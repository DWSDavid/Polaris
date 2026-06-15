from src.data import account


def test_save_load(tmp_path):
    account.ACCOUNT_PATH = tmp_path / "account.json"
    data = {
        "total_assets": 3143.0,
        "debt": 1860.0,
        "cash": 0.0,
        "annual_rate": 0.035,
        "warning_line": 1.50,
        "liquidation_line": 1.30,
        "holdings": [
            {"code": "601688", "name": "华泰证券", "shares": 159.21, "cost": 22.7}
        ],
    }
    account.save(data)
    got = account.load()
    assert got["debt"] == 1860.0
    assert got["holdings"][0]["name"] == "华泰证券"


def test_load_missing_returns_defaults(tmp_path):
    account.ACCOUNT_PATH = tmp_path / "nope.json"
    defaults = account.load()
    assert defaults["warning_line"] == 1.50
    assert defaults["holdings"] == []
