"""Upload validation: clear messages for bad files, nothing imported silently wrong."""

import pytest

from sic.data import upload

HEADER = "invoice_id,invoice_date,product_id,quantity,unit_price\n"


def check(data_dir, body: str, day_first=False, mapping=None, currency="GBP", header=HEADER):
    staged = upload.stage((header + body).encode(), "t.csv")
    options = upload.Options(mapping or staged["suggested_mapping"], currency, day_first)
    return staged, upload.validate(staged["upload_id"], options)


def codes(result) -> dict:
    return {i["code"]: i["rows"] for i in result["issues"]}


def test_mapping_suggestions_recognise_common_headers():
    mapping = upload.suggest_mapping(
        [
            "InvoiceNo",
            "InvoiceDate",
            "StockCode",
            "Description",
            "Quantity",
            "UnitPrice",
            "CustomerID",
            "Country",
        ]
    )
    assert mapping == {
        "invoice_id": "InvoiceNo",
        "invoice_date": "InvoiceDate",
        "product_id": "StockCode",
        "quantity": "Quantity",
        "unit_price": "UnitPrice",
        "product_name": "Description",
        "customer_id": "CustomerID",
        "country": "Country",
        "currency": None,
    }


def test_bad_values_are_counted_with_row_numbers(data_dir):
    _, result = check(
        data_dir,
        "1,2024-01-01,A,2,1.50\n2,not a date,A,1,1\n3,2024-01-02,A,x,1\n"
        '4,2024-01-03,A,1,"2,50"\n,2024-01-04,A,1,1\n',
    )
    issues = codes(result)
    assert issues["unparseable_date"] == 1
    assert issues["non_numeric_quantity"] == 1
    assert issues["non_numeric_price"] == 1  # decimal comma is rejected, not guessed
    assert issues["missing_invoice_id"] == 1
    assert (result["rows_total"], result["rows_usable"]) == (5, 1)
    example = next(i for i in result["issues"] if i["code"] == "unparseable_date")["examples"][0]
    assert example == {"row": 3, "value": "not a date"}


def test_thousands_separators_and_currency_symbols(data_dir):
    _, result = check(data_dir, '1,2024-01-01,A,2,"£1,234.50"\n')
    assert result["rows_usable"] == 1
    assert result["line_types"][0]["value"] == 2469.0


def test_date_order(data_dir):
    body = "1,05/02/2024,A,1,1\n2,25/02/2024,A,1,1\n3,2024-02-07,A,1,1\n"
    _, month_first = check(data_dir, body)
    assert codes(month_first)["date_order_conflict"] == 1  # 25/02 cannot be month-first
    _, day_first = check(data_dir, body, day_first=True)
    assert "date_order_conflict" not in codes(day_first)
    dates = [r["invoice_ts"][:10] for r in day_first["preview"]]
    assert dates == ["2024-02-05", "2024-02-25", "2024-02-07"]  # ISO stays ISO


def test_missing_required_mapping_is_an_error(data_dir):
    staged = upload.stage((HEADER + "1,2024-01-01,A,1,1\n").encode(), "t.csv")
    mapping = {**staged["suggested_mapping"], "unit_price": None}
    with pytest.raises(upload.UploadError, match="unit_price"):
        upload.validate(staged["upload_id"], upload.Options(mapping, "GBP"))


def test_mixed_currencies_are_rejected(data_dir):
    header = HEADER.strip() + ",currency\n"
    with pytest.raises(upload.UploadError, match="mixes currencies"):
        check(data_dir, "1,2024-01-01,A,1,1,GBP\n2,2024-01-01,A,1,1,EUR\n", header=header)
    with pytest.raises(upload.UploadError, match="currency column says EUR"):
        check(data_dir, "1,2024-01-01,A,1,1,EUR\n", header=header)


@pytest.mark.parametrize("currency", ["", "pounds", "G1P"])
def test_currency_code_is_required(data_dir, currency):
    with pytest.raises(upload.UploadError, match="3-letter"):
        check(data_dir, "1,2024-01-01,A,1,1\n", currency=currency)


def test_unreadable_files(data_dir):
    with pytest.raises(upload.UploadError, match="empty"):
        upload.stage(b"   ", "t.csv")
    with pytest.raises(upload.UploadError, match="column"):
        upload.stage(b"a,b\n1,2\n", "t.csv")


def test_windows_encoded_file_is_read(data_dir):
    raw = (HEADER.strip() + ",product_name\n1,2024-01-01,A,1,1,Café\n").encode("cp1252")
    staged = upload.stage(raw, "t.csv")
    assert staged["encoding"] == "cp1252"


def test_uploaded_text_is_only_data(data_dir, make_upload):
    """Formula- or SQL-like text is stored verbatim, never interpreted."""
    from sic.data import storage

    dataset = make_upload(
        "invoice_id,invoice_date,product_id,product_name,quantity,unit_price\n"
        '1,2024-01-01,A,"=HYPERLINK(""x""); DROP TABLE lines; --",1,1\n'
    )
    with storage.connect(dataset) as con:
        name = con.execute("SELECT product_name FROM lines").fetchone()[0]
        assert name.startswith("=HYPERLINK") and "DROP TABLE" in name
        assert con.execute("SELECT count(*) FROM lines").fetchone()[0] == 1
