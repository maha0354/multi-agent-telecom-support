import pytest

from app.data.seed import seed
from app.tools.roaming import compare_roaming_options


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "telecom.db"
    seed(path)
    return path


def costs(result: dict) -> dict[str, float]:
    return {o["option"]: o["total_cost_sek"] for o in result["options"]}


def test_japan_ten_days_compares_every_option(db):
    result = compare_roaming_options("C-1001", zone=4, days=10, db_path=db)
    assert result["estimated_gb"] == 6.0  # 18 GB/month / 30 * 10
    assert costs(result) == {
        "Pay-as-you-go on the current plan": 774.0,
        "2 x Travel Pass Asia-Pacific 7 days": 498,
        "Travel Pass Asia-Pacific 15 days": 399,
        "Upgrade to World 150 GB for one month, downgrade after the trip": 300,
    }
    assert result["cheapest_option"]["type"] == "plan_upgrade"
    assert [o["total_cost_sek"] for o in result["options"]] == sorted(costs(result).values())


def test_pass_overflow_is_charged_pay_as_you_go(db):
    result = compare_roaming_options("C-1001", zone=4, days=7, gb_per_day=1, db_path=db)
    # 7 GB needed; the 7-day pass has 5 GB, so 2 GB at 129 SEK/GB on top of 249 SEK.
    assert costs(result)["Travel Pass Asia-Pacific 7 days"] == 249 + 2 * 129


def test_zone_already_included_costs_nothing(db):
    result = compare_roaming_options("C-1001", zone=2, days=10, db_path=db)
    assert result["cheapest_option"]["total_cost_sek"] == 0
    assert len(result["options"]) == 1


@pytest.mark.parametrize("zone, days", [(9, 10), (4, 0)])
def test_invalid_input_returns_error(db, zone, days):
    assert "error" in compare_roaming_options("C-1001", zone=zone, days=days, db_path=db)


def test_zone_already_in_plan_for_world_customer(db):
    result = compare_roaming_options("C-1003", zone=4, days=10, db_path=db)
    assert result["cheapest_option"]["type"] == "included"


def test_zone_5_has_no_plan_upgrade_option(db):
    result = compare_roaming_options("C-1001", zone=5, days=7, db_path=db)
    assert {o["type"] for o in result["options"]} == {"pay_as_you_go", "travel_pass"}
    # 18 GB/month -> 4.2 GB in 7 days: the 3 GB pass needs 1.2 GB pay-as-you-go on top.
    assert costs(result)["Travel Pass South America & Africa 7 days"] == round(299 + 1.2 * 179, 2)
