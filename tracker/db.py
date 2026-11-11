"""SQLite price log: one snapshot per calendar day (re-running a day replaces it)."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .models import FetchResult, Leg, Quote

SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    run_date TEXT NOT NULL, dest TEXT NOT NULL, rank INTEGER NOT NULL,
    airline TEXT, fare REAL, bag_fee REAL, total REAL, bag_included INTEGER, bag_note TEXT,
    outbound TEXT, inbound TEXT, links TEXT, source TEXT, seller TEXT, booking_url TEXT, fetched_at TEXT,
    PRIMARY KEY (run_date, dest, rank)
);
CREATE TABLE IF NOT EXISTS source_status (
    run_date TEXT NOT NULL, source TEXT NOT NULL, dest TEXT NOT NULL, status TEXT, message TEXT,
    PRIMARY KEY (run_date, source, dest)
);
CREATE TABLE IF NOT EXISTS status (
    run_date TEXT NOT NULL, dest TEXT NOT NULL, status TEXT, message TEXT, fetched_at TEXT,
    PRIMARY KEY (run_date, dest)
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    have = {r["name"] for r in con.execute("PRAGMA table_info(quotes)")}
    for col in ("seller", "booking_url", "fetched_at"):          # upgrade databases created by older versions
        if col not in have:
            con.execute(f"ALTER TABLE quotes ADD COLUMN {col} TEXT")
    return con


def save(con, run_date: date, results: list[FetchResult], source_status: list[tuple] = ()) -> None:
    """`source_status` rows are (source, dest, status, message)."""
    d = run_date.isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    with con:
        for src, dest, st, msg in source_status:
            con.execute("INSERT OR REPLACE INTO source_status VALUES (?,?,?,?,?)", (d, src, dest, st, msg))
        for r in results:
            if r.status == "error" and con.execute(
                    "SELECT 1 FROM quotes WHERE run_date=? AND dest=?", (d, r.dest)).fetchone():
                continue                      # keep an earlier good snapshot from today
            con.execute("DELETE FROM quotes WHERE run_date=? AND dest=?", (d, r.dest))
            con.execute("INSERT OR REPLACE INTO status VALUES (?,?,?,?,?)",
                        (d, r.dest, r.status, r.message, now))
            for i, q in enumerate(r.quotes):
                con.execute(
                    "INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d, r.dest, i, q.airline, q.fare_per_pax, q.bag_fee_per_pax, q.total_per_pax,
                     int(q.bag_included), q.bag_note, json.dumps(q.outbound.to_dict()),
                     json.dumps(q.inbound.to_dict()), json.dumps(q.links), q.source, q.seller, q.booking_url, now))


def _quote(row) -> Quote:
    return Quote(dest=row["dest"], outbound=Leg.from_dict(json.loads(row["outbound"])),
                 inbound=Leg.from_dict(json.loads(row["inbound"])), fare_per_pax=row["fare"],
                 bag_fee_per_pax=row["bag_fee"], bag_included=bool(row["bag_included"]),
                 bag_note=row["bag_note"] or "", links=json.loads(row["links"]), source=row["source"] or "", seller=row["seller"] or "",
                 booking_url=row["booking_url"] or "")


def latest_date(con) -> date | None:
    row = con.execute("SELECT MAX(run_date) m FROM status").fetchone()
    return date.fromisoformat(row["m"]) if row and row["m"] else None


def quotes_on(con, run_date: date, dest: str) -> list[Quote]:
    rows = con.execute("SELECT * FROM quotes WHERE run_date=? AND dest=? ORDER BY rank",
                       (run_date.isoformat(), dest)).fetchall()
    return [_quote(r) for r in rows]


def status_on(con, run_date: date, dest: str) -> tuple[str, str]:
    row = con.execute("SELECT status, message FROM status WHERE run_date=? AND dest=?",
                      (run_date.isoformat(), dest)).fetchone()
    return (row["status"], row["message"] or "") if row else ("missing", "Not fetched")


def fetched_at(con, run_date: date) -> str:
    """ISO timestamp of the most recent fetch stored for this day."""
    row = con.execute("SELECT MAX(fetched_at) m FROM status WHERE run_date=?", (run_date.isoformat(),)).fetchone()
    return (row["m"] if row else "") or ""


def sources_on(con, run_date: date) -> dict[str, dict[str, int]]:
    """{source: {status: count}} for the day's fetch."""
    out: dict[str, dict[str, int]] = {}
    for r in con.execute("SELECT source, status, COUNT(*) n FROM source_status WHERE run_date=? GROUP BY source, status",
                         (run_date.isoformat(),)):
        out.setdefault(r["source"], {})[r["status"]] = r["n"]
    return out


def offers(con, run_date: date, pax: int = 4) -> list[dict]:
    """Every stored itinerary for the day in one flat, normalised shape (one row per direction-pair)."""
    rows = con.execute("SELECT * FROM quotes WHERE run_date=? ORDER BY dest, rank", (run_date.isoformat(),)).fetchall()
    out = []
    for r in rows:
        o, i = json.loads(r["outbound"]), json.loads(r["inbound"])
        links = json.loads(r["links"])
        out.append({
            "destination": r["dest"], "airline": r["airline"],
            "flight_number": f'{o["flight_number"]} / {i["flight_number"]}',
            "price_1_pax": r["total"], "price_4_pax": round(r["total"] * pax, 2),
            "fare_1_pax": r["fare"], "bag_fee_1_pax": r["bag_fee"],
            "departure_time": o["depart_time"], "arrival_time": o["arrive_time"],
            "return_departure_time": i["depart_time"], "return_arrival_time": i["arrive_time"],
            "is_direct": True, "includes_baggage": True, "baggage_in_fare": bool(r["bag_included"]),
            "source_platform": r["seller"] or r["source"], "data_source": r["source"],
            "booking_link": r["booking_url"] or next(iter(links.values()), ""),
            "timestamp": r["fetched_at"],
        })
    return out


def history(con, dest: str, upto: date) -> list[tuple[date, float]]:
    """Cheapest bag-inclusive price per day, oldest first, up to and including `upto`."""
    rows = con.execute("SELECT run_date, MIN(total) t FROM quotes WHERE dest=? AND run_date<=? "
                       "GROUP BY run_date ORDER BY run_date", (dest, upto.isoformat())).fetchall()
    return [(date.fromisoformat(r["run_date"]), r["t"]) for r in rows]
