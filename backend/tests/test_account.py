import pytest

from app.data.seed import seed
from app.tools.account import find_plans, get_my_account, get_outages, get_roaming_rate


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "telecom.db"
    seed(path)
    return path


def test_demo_account_excludes_japan_zone(db):
    account = get_my_account("C-1001", db_path=db)
    assert account["plan_id"] == "plus"
    assert 4 not in account["zones"]
    assert account["data_left_this_month_gb"] == 17.6


def test_unknown_customer_returns_error(db):
    assert "error" in get_my_account("C-9999", db_path=db)


def test_find_plans_filters_by_zone(db):
    assert [p["id"] for p in find_plans(zone=4, db_path=db)] == ["world"]
    assert [p["id"] for p in find_plans(zone=2, db_path=db)] == ["plus", "max", "world"]


def test_find_plans_filters_by_data(db):
    assert {p["id"] for p in find_plans(min_data_gb=100, db_path=db)} == {"max", "world"}


def test_roaming_rate_includes_passes(db):
    rate = get_roaming_rate(4, db_path=db)
    assert rate["price_per_gb_sek"] == 129.0
    assert [p["id"] for p in rate["travel_passes"]] == ["z4-7d", "z4-15d"]


def test_unknown_zone_returns_error(db):
    assert "error" in get_roaming_rate(9, db_path=db)


def test_outages_case_insensitive_ongoing_first(db):
    assert get_outages(" uppsala ", db_path=db)[0]["status"] == "ongoing"
    assert get_outages("Stockholm", db_path=db) == []
