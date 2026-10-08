"""Trip cost comparison. The decision is made in code so the cheapest option is never
the LLM's own reasoning; the analyst reports what this returns."""

import math
from pathlib import Path

from app.config import DB_PATH
from app.tools.account import find_plans, get_my_account, get_roaming_rate

DAYS_PER_MONTH = 30


def compare_roaming_options(customer_id: str, zone: int, days: int, gb_per_day: float | None = None,
                            db_path: Path = DB_PATH) -> dict:
    """Every way to cover a trip's data in a zone, with total cost in SEK, cheapest first.

    Usage is estimated from the customer's typical monthly usage unless gb_per_day is given.
    Each option covers the whole trip: passes are repeated to cover the days, and data beyond
    a pass's allowance is charged pay-as-you-go. A plan upgrade costs the monthly price
    difference (an upper bound: upgrades are charged pro rata, and you can downgrade after).
    Simplification: the Zone 4 fair-use limit (20 GB/month) is not applied.
    """
    if days <= 0:
        return {"error": "days must be positive"}
    account = get_my_account(customer_id, db_path)
    if "error" in account:
        return account
    rate = get_roaming_rate(zone, db_path)
    if "error" in rate:
        return rate

    if gb_per_day is None:
        gb_per_day = account["typical_monthly_usage_gb"] / DAYS_PER_MONTH
        usage_basis = f"typical usage {account['typical_monthly_usage_gb']} GB/month"
    else:
        usage_basis = "usage stated by the customer"
    gb_needed = round(gb_per_day * days, 2)

    base = {"zone": zone, "zone_name": rate["zone_name"], "days": days,
            "estimated_gb": gb_needed, "usage_basis": usage_basis, "current_plan": account["plan_name"]}

    if zone in account["zones"]:
        option = {"option": f"Current plan {account['plan_name']} (zone included)", "type": "included",
                  "total_cost_sek": 0, "calculation": "included in the current plan"}
        return {**base, "options": [option], "cheapest_option": option}

    price = rate["price_per_gb_sek"]
    options = [{
        "option": "Pay-as-you-go on the current plan", "type": "pay_as_you_go",
        "total_cost_sek": round(gb_needed * price, 2),
        "calculation": f"{gb_needed} GB x {price} SEK/GB",
    }]

    for p in rate["travel_passes"]:
        count = math.ceil(days / p["days"])
        overflow_gb = round(max(0.0, gb_needed - count * p["data_gb"]), 2)
        calculation = f"{count} x {p['price_sek']} SEK ({count * p['data_gb']} GB)"
        if overflow_gb:
            calculation += f" + {overflow_gb} GB x {price} SEK/GB pay-as-you-go"
        options.append({
            "option": f"{count} x {p['name']}" if count > 1 else p["name"], "type": "travel_pass",
            "total_cost_sek": round(count * p["price_sek"] + overflow_gb * price, 2),
            "calculation": calculation,
        })

    for plan in find_plans(zone=zone, db_path=db_path):
        difference = plan["monthly_price_sek"] - account["monthly_price_sek"]
        options.append({
            "option": f"Upgrade to {plan['name']} for one month, downgrade after the trip", "type": "plan_upgrade",
            "total_cost_sek": max(difference, 0),
            "calculation": f"{plan['monthly_price_sek']} - {account['monthly_price_sek']} SEK monthly difference (upper bound)",
        })

    options.sort(key=lambda o: o["total_cost_sek"])
    return {**base, "options": options, "cheapest_option": options[0]}
