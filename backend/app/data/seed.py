"""Create the fictional operator database. Run with: uv run python -m app.data.seed"""

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
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
    status TEXT NOT NULL,            -- ongoing | planned | resolved
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
    (5, "South America and Africa", 179.0),
]

TRAVEL_PASSES = [
    ("z2-7d", 2, "Travel Pass Europe 7 days", 5, 7, 99),
    ("z3-7d", 3, "Travel Pass North America 7 days", 5, 7, 199),
    ("z3-15d", 3, "Travel Pass North America 15 days", 10, 15, 349),
    ("z4-7d", 4, "Travel Pass Asia-Pacific 7 days", 5, 7, 249),
    ("z4-15d", 4, "Travel Pass Asia-Pacific 15 days", 10, 15, 399),
    ("z5-7d", 5, "Travel Pass South America & Africa 7 days", 3, 7, 299),
    ("z5-15d", 5, "Travel Pass South America & Africa 15 days", 8, 15, 549),
]

# Demo customers selectable in the UI. Each one makes a different scenario possible.
CUSTOMERS = [
    # Plus (zones 1-2): a Japan trip needs a comparison; ongoing outage in Uppsala.
    ("C-1001", "Alex Demo", "plus", "Uppsala", 12.4, 18.0, 500),
    # Bas (zone 1 only): almost out of data, and even Zone 2 costs extra.
    ("C-1002", "Sara Demo", "bas", "Malmö", 9.6, 11.0, 500),
    # World (zones 1-4): Japan is already included.
    ("C-1003", "Johan Demo", "world", "Stockholm", 40.0, 60.0, 500),
    # Max (zones 1-3): the USA is included, Thailand is not; 5G outage in Kiruna.
    ("C-1004", "Lina Demo", "max", "Kiruna", 30.0, 45.0, 500),
    # Bas: allowance used up (reduced speed) and an outage in his area.
    ("C-1005", "Omar Demo", "bas", "Göteborg", 10.0, 8.0, 500),
]

# (id, area, service, status, start offset hours, end offset hours or None, description).
# Times are relative to when the database is seeded, so "ongoing" outages stay current.
OUTAGES_RELATIVE = [
    (1, "Uppsala", "mobile data", "ongoing", -4, 6,
     "Reduced 4G/5G data speeds after a fibre cut to two base stations."),
    (2, "Malmö", "calls and data", "resolved", -98, -93, "Planned maintenance."),
    (3, "Kiruna", "mobile data", "ongoing", -20, None,
     "No 5G coverage in the city centre; 4G unaffected."),
    (4, "Göteborg", "calls and data", "ongoing", -2, 3,
     "Calls and data unavailable in Hisingen after a power cut at a radio site."),
    (5, "Stockholm", "mobile data", "planned", 30, 34,
     "Planned night-time maintenance in Södermalm; short interruptions possible."),
    (6, "Luleå", "mobile data", "ongoing", -6, 2, "Slow 4G data speeds due to network congestion."),
    (7, "Umeå", "calls", "resolved", -50, -47, "Calls to some numbers failed after a software update."),
]


def _outages(now: datetime) -> list[tuple]:
    fmt = "%Y-%m-%d %H:%M"
    return [
        (oid, area, service, status, (now + timedelta(hours=start)).strftime(fmt),
         None if end is None else (now + timedelta(hours=end)).strftime(fmt), description)
        for oid, area, service, status, start, end, description in OUTAGES_RELATIVE
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
        conn.executemany("INSERT INTO outages VALUES (?, ?, ?, ?, ?, ?, ?)", _outages(datetime.now()))


if __name__ == "__main__":
    seed()
    print(f"Seeded {DB_PATH}")
