"""Create the fictional operator database. Run with: uv run python -m app.data.seed"""

import sqlite3
from contextlib import closing
from pathlib import Path

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE plans (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    monthly_price_sek INTEGER NOT NULL,
    data_gb INTEGER NOT NULL,
    zones TEXT NOT NULL              -- comma-separated included roaming zones, e.g. "1,2"
);
CREATE TABLE roaming_rates (
    zone INTEGER PRIMARY KEY,
    zone_name TEXT NOT NULL,
    price_per_gb_sek REAL            -- NULL for Zone 1 (always included)
);
CREATE TABLE travel_passes (
    id TEXT PRIMARY KEY,
    zone INTEGER NOT NULL REFERENCES roaming_rates(zone),
    name TEXT NOT NULL,
    data_gb INTEGER NOT NULL,
    days INTEGER NOT NULL,
    price_sek INTEGER NOT NULL
);
CREATE TABLE customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    area TEXT NOT NULL,
    data_used_this_month_gb REAL NOT NULL,
    typical_monthly_usage_gb REAL NOT NULL,
    roaming_spend_limit_sek INTEGER NOT NULL
);
CREATE TABLE outages (
    id INTEGER PRIMARY KEY,
    area TEXT NOT NULL,
    service TEXT NOT NULL,
    status TEXT NOT NULL,            -- ongoing | resolved
    started_at TEXT NOT NULL,
    expected_end TEXT,
    description TEXT NOT NULL
);
"""

PLANS = [
    ("bas", "Bas 10 GB", 199, 10, "1"),
    ("plus", "Plus 30 GB", 299, 30, "1,2"),
    ("max", "Max 100 GB", 449, 100, "1,2,3"),
    ("world", "World 150 GB", 599, 150, "1,2,3,4"),
]

ROAMING_RATES = [
    (1, "EU and EEA", None),
    (2, "Europe outside the EU", 49.0),
    (3, "North America", 89.0),
    (4, "Asia-Pacific", 129.0),
]

TRAVEL_PASSES = [
    ("z2-7d", 2, "Travel Pass Europe 7 days", 5, 7, 99),
    ("z3-7d", 3, "Travel Pass North America 7 days", 5, 7, 199),
    ("z3-15d", 3, "Travel Pass North America 15 days", 10, 15, 349),
    ("z4-7d", 4, "Travel Pass Asia-Pacific 7 days", 5, 7, 249),
    ("z4-15d", 4, "Travel Pass Asia-Pacific 15 days", 10, 15, 399),
]

# The demo customer is on Plus (zones 1-2), so a trip to Japan (Zone 4) gives the
# analyst a reason to compare pay-as-you-go, Travel Passes and plan upgrades.
CUSTOMERS = [
    ("C-1001", "Alex Demo", "plus", "Uppsala", 12.4, 18.0, 500),
]

OUTAGES = [
    (1, "Uppsala", "mobile data", "ongoing", "2026-10-07 06:30",
     "2026-10-07 18:00", "Reduced 4G/5G data speeds after a fibre cut to two base stations."),
    (2, "Malmö", "calls and data", "resolved", "2026-10-03 22:00",
     "2026-10-04 03:00", "Planned maintenance."),
    (3, "Kiruna", "mobile data", "ongoing", "2026-10-06 14:00",
     None, "No 5G coverage in the city centre; 4G unaffected."),
]


def seed(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO plans VALUES (?, ?, ?, ?, ?)", PLANS)
        conn.executemany("INSERT INTO roaming_rates VALUES (?, ?, ?)", ROAMING_RATES)
        conn.executemany("INSERT INTO travel_passes VALUES (?, ?, ?, ?, ?, ?)", TRAVEL_PASSES)
        conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)", CUSTOMERS)
        conn.executemany("INSERT INTO outages VALUES (?, ?, ?, ?, ?, ?, ?)", OUTAGES)


if __name__ == "__main__":
    seed()
    print(f"Seeded {DB_PATH}")
