"""The UCI cleaning rules, checked on a small hand-made table with one row per case."""

import pandas as pd
import pytest

from sic.data import storage, uci

S1, S2 = uci.SHEETS


def row(
    invoice,
    code,
    qty,
    price,
    ts="2010-12-06 10:00",
    desc="ITEM",
    customer=17850.0,
    country="United Kingdom",
    sheet=S2,
):
    return {
        "Invoice": invoice,
        "StockCode": code,
        "Description": desc,
        "Quantity": qty,
        "InvoiceDate": pd.Timestamp(ts),
        "Price": price,
        "Customer ID": customer,
        "Country": country,
        "source_sheet": sheet,
    }


# (row, expected line type)
CASES = [
    (row("536365", "85123A", 6, 2.55, desc="WHITE HEART"), "product_sale"),
    (row("536366", "85123a", 2, 2.55, desc="WHITE HEART"), "product_sale"),  # lower-case code
    (row("536367", " 47503J ", 1, 4.0), "product_sale"),  # stray spaces in code
    (row("C536379", "85123A", -1, 2.55), "product_return"),
    (row("C536380", "M", -1, 100.0, desc="Manual"), "manual_adjustment"),
    (row("C536381", "M", 1, 50.0, desc="Manual", customer=None), "manual_adjustment"),
    (row("536382", "POST", 1, 18.0), "shipping"),
    (row("536383", "DOT", 1, 30.0), "shipping"),
    (row("536384", "C2", 1, 50.0), "shipping"),
    (row("C536385", "AMAZONFEE", -1, 500.0), "fees_commission"),
    (row("C536386", "BANK CHARGES", -1, 15.0), "fees_commission"),
    (row("C536387", "CRUK", -1, 20.0), "fees_commission"),
    (row("C536388", "D", -1, 10.0, desc="Discount"), "discount"),
    (row("C536389", "S", -1, 5.0, desc="SAMPLES"), "samples"),
    (row("536390", "gift_0001_20", 1, 17.39), "gift_voucher"),
    (row("536391", "TEST001", 1, 4.5), "test"),
    (
        row("A563185", "B", 1, -11062.06, desc="Adjust bad debt", customer=None),
        "bad_debt_adjustment",
    ),
    (row("536392", "21000", -5, 0.0, desc="damages", customer=None), "zero_value_stock_note"),
    (row("536393", "21002", 4, 0.0, customer=None), "zero_price_line"),
    (row("581483", "23843", 80995, 2.08, desc="PAPER CRAFT"), "product_sale"),  # unusual
    # A negative quantity at a non-zero price without a C invoice matches no rule:
    # it must NOT be assumed to be a stock note.
    (row("536394", "21001", -3, 1.0), "unclassified"),
]
OVERLAP_ROW = row("536400", "22000", 2, 3.0, ts="2010-12-02 09:00")


def frame(rows):
    df = pd.DataFrame(rows)
    df["source_row"] = df.groupby("source_sheet").cumcount() + 2
    return df


def sheet_rows(overlap_change=None):
    first_sheet = [
        row("489434", "85048", 12, 6.95, ts="2009-12-01 07:45", sheet=S1),
        {**OVERLAP_ROW, "source_sheet": S1, **(overlap_change or {})},
    ]
    second_sheet = [OVERLAP_ROW, *[c[0] for c in CASES], CASES[0][0]]  # last: exact duplicate
    return frame(first_sheet + second_sheet)


SOURCE = {"file": "test.xlsx", "sha256": "0" * 64}


def build(data_dir, rows):
    return uci.build_from_frame(rows, {"numeric_descriptions": 0}, SOURCE)


def test_every_row_is_classified_and_counts_reconcile(data_dir):
    quality = build(data_dir, sheet_rows())
    flow = quality["row_flow"]
    assert flow["rows_read"] == 2 + 1 + len(CASES) + 1
    assert flow["sheet_overlap_removed"] == 1
    assert flow["rows_kept"] == flow["rows_read"] - 1 == flow["rows_by_line_type_total"]
    assert flow["reconciles"] is True


def test_each_case_gets_the_expected_line_type(data_dir):
    build(data_dir, sheet_rows())
    con = storage.connect("uci")
    got = con.execute(
        "SELECT invoice_id, product_id, line_type FROM lines WHERE source_sheet = ? "
        "ORDER BY source_row",
        [S2],
    ).fetchall()
    # rows: overlap row, the cases, the duplicate
    for (invoice, _, line_type), (case, expected) in zip(got[1:-1], CASES, strict=True):
        assert invoice == case["Invoice"].strip()
        assert line_type == expected, case


def test_codes_are_normalised_and_names_come_from_sale_lines(data_dir):
    build(data_dir, sheet_rows())
    con = storage.connect("uci")
    codes = {r[0] for r in con.execute("SELECT DISTINCT product_id FROM lines").fetchall()}
    assert "85123A" in codes and "85123a" not in codes
    assert "47503J" in codes
    name = con.execute(
        "SELECT DISTINCT product_name FROM lines WHERE product_id = '21000'"
    ).fetchone()[0]
    assert name == "damages"  # no sale lines exist for 21000, so the note is the only description


def test_duplicates_and_unusual_lines_are_flagged_not_removed(data_dir):
    quality = build(data_dir, sheet_rows())
    con = storage.connect("uci")
    assert con.execute("SELECT count(*) FROM lines WHERE is_duplicate").fetchone()[0] == 1
    assert quality["flags"]["exact_duplicate_copies"]["rows"] == 1
    unusual = con.execute("SELECT invoice_id FROM lines WHERE is_unusual").fetchall()
    assert unusual == [("581483",)]


def test_sheet_overlap_must_be_identical(data_dir):
    with pytest.raises(ValueError, match="overlapping period differs"):
        build(data_dir, sheet_rows(overlap_change={"Quantity": 99}))
