"""Fixed queries against the operator database. No free-form SQL reaches the LLM."""

import sqlite3
from contextlib import closing
from pathlib import Path

from app.config import DB_PATH


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _plan_dict(row: sqlite3.Row) -> dict:
    plan = dict(row)
    plan["zones"] = [int(z) for z in plan["zones"].split(",")]
    return plan


def list_customers(db_path: Path = DB_PATH) -> list[dict]:
    """Demo customers for the simulated login picker. Never exposed to the LLM."""
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, c.area, p.name AS plan_name
               FROM customers c JOIN plans p ON p.id = c.plan_id ORDER BY c.id"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_my_account(customer_id: str, db_path: Path = DB_PATH) -> dict:
    """Account and plan for the logged-in customer. customer_id comes from graph state, not the LLM."""
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            """SELECT c.*, p.name AS plan_name, p.monthly_price_sek, p.data_gb, p.zones
               FROM customers c JOIN plans p ON p.id = c.plan_id WHERE c.id = ?""",
            (customer_id,),
        ).fetchone()
    if row is None:
        return {"error": "No account found for the logged-in customer"}
    account = _plan_dict(row)
    account["data_left_this_month_gb"] = round(account["data_gb"] - account["data_used_this_month_gb"], 2)
    return account


def find_plans(zone: int | None = None, min_data_gb: int | None = None, db_path: Path = DB_PATH) -> list[dict]:
    """All plans, optionally only those that include a roaming zone and/or have enough data."""
    with closing(_connect(db_path)) as conn:
        rows = conn.execute("SELECT * FROM plans ORDER BY monthly_price_sek").fetchall()
    plans = [_plan_dict(r) for r in rows]
    if zone is not None:
        plans = [p for p in plans if zone in p["zones"]]
    if min_data_gb is not None:
        plans = [p for p in plans if p["data_gb"] >= min_data_gb]
    return plans


def get_roaming_rate(zone: int, db_path: Path = DB_PATH) -> dict:
    """Pay-as-you-go price per GB and the Travel Passes available for one zone."""
    with closing(_connect(db_path)) as conn:
        rate = conn.execute("SELECT * FROM roaming_rates WHERE zone = ?", (zone,)).fetchone()
        passes = conn.execute(
            "SELECT id, name, data_gb, days, price_sek FROM travel_passes WHERE zone = ? ORDER BY price_sek",
            (zone,),
        ).fetchall()
        zones = [r[0] for r in conn.execute("SELECT zone FROM roaming_rates ORDER BY zone")]
    if rate is None:
        return {"error": f"Unknown roaming zone {zone}. Valid zones are {zones[0]}-{zones[-1]}."}
    return {**dict(rate), "travel_passes": [dict(p) for p in passes]}


def get_outages(area: str, db_path: Path = DB_PATH) -> list[dict]:
    """Known outages for an area (case-insensitive), ongoing first."""
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            """SELECT * FROM outages WHERE lower(area) = lower(?)
               ORDER BY CASE status WHEN 'ongoing' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END, started_at DESC""",
            (area.strip(),),
        ).fetchall()
    return [dict(r) for r in rows]
