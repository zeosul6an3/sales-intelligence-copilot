import pytest

from sic.data import storage, upload
from sic.data.storage import DATA_DIR as REAL_DATA_DIR

# Small dataset with hand-calculated expected values (see test_metrics.py).
# 2024-01-01 is a Monday; the data ends on Thursday 2024-02-08.
METRICS_CSV = """\
invoice_id,invoice_date,product_id,product_name,quantity,unit_price,customer_id,country
1001,2024-01-01,A,Alpha,10,2.00,C1,UK
1001,2024-01-01,B,Beta,1,5.00,C1,UK
1002,2024-01-03,A,Alpha,5,2.00,C2,France
1003,2024-01-09,B,Beta,4,5.00,,UK
R1,2024-01-10,A,Alpha,-2,2.00,C1,UK
1004,2024-02-05,A,Alpha,3,2.00,C2,France
1005,2024-02-06,C,Gamma,1,0,C3,UK
1006,2024-02-07,C,Gamma,0,3.00,C3,UK
1007,2024-02-08,C,Gamma,1,-3.00,C3,UK
"""


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point all dataset storage at a temporary folder for the test."""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def make_upload(data_dir):
    def _make(csv_text: str, currency: str = "GBP", day_first: bool = False, name=None) -> str:
        staged = upload.stage(csv_text.encode("utf-8"), "test.csv")
        options = upload.Options(staged["suggested_mapping"], currency, day_first, name)
        return upload.import_upload(staged["upload_id"], options)["id"]

    return _make


@pytest.fixture
def real_uci():
    """The real built-in dataset, if it has been prepared on this computer."""
    if not (REAL_DATA_DIR / "processed" / "uci" / "warehouse.duckdb").is_file():
        pytest.skip("UCI data not prepared; run scripts/download_data.py and prepare_data.py")
    return REAL_DATA_DIR / "processed" / "uci"
