"""Configuration loading."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Destination:
    code: str
    name: str
    country: str
    airports: list[str] = field(default_factory=list)
    tag: str = ""                   # short descriptor, e.g. Hub / Island
    note: str = ""
    primary: bool = False
    google: str = ""                # names used in booking-link searches
    kayak: str = ""
    skyscanner: str = ""
    experience_score: float = 7.0
    daily_ground_cost: float = 100.0

    def __post_init__(self):
        self.airports = self.airports or [self.code]
        self.google = self.google or self.airports[0]
        self.kayak = self.kayak or self.airports[0]
        self.skyscanner = (self.skyscanner or self.airports[0]).lower()

    @property
    def airport_label(self) -> str:
        return " / ".join(self.airports)


@dataclass
class Trip:
    origin: str
    depart_date: date
    return_date: date
    outbound_arrive_by: time
    return_arrive_by: time
    pax: list[int]
    currency: str = "SGD"
    symbol: str = "S$"

    @property
    def nights(self) -> int:
        return (self.return_date - self.depart_date).days


@dataclass
class Config:
    trip: Trip
    destinations: list[Destination]
    provider: dict = field(default_factory=dict)
    baggage: dict = field(default_factory=dict)
    deals: dict = field(default_factory=dict)
    schedule: dict = field(default_factory=dict)
    database: Path = ROOT / "data" / "prices.db"

    def dest(self, code: str) -> Destination:
        return next(d for d in self.destinations if d.code == code)


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _as_time(v) -> time:
    return datetime.strptime(str(v), "%H:%M").time()


def load_env(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader (no extra dependency). Existing env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config(path: str | Path | None = None) -> Config:
    load_env()
    path = Path(path) if path else ROOT / "config.yaml"
    raw = yaml.safe_load(path.read_text())
    t = raw["trip"]
    trip = Trip(
        origin=t["origin"],
        depart_date=_as_date(t["depart_date"]),
        return_date=_as_date(t["return_date"]),
        outbound_arrive_by=_as_time(t["outbound_arrive_by"]),
        return_arrive_by=_as_time(t["return_arrive_by"]),
        pax=list(t.get("pax", [1, 4])),
        currency=t.get("currency", "SGD"),
        symbol=t.get("symbol", "S$"),
    )
    db = Path(raw.get("database", "data/prices.db"))
    if not db.is_absolute():
        db = ROOT / db
    return Config(
        trip=trip,
        destinations=[Destination(**d) for d in raw["destinations"]],
        provider=raw.get("provider", {}),
        baggage=raw.get("baggage", {}),
        deals=raw.get("deals", {}),
        schedule=raw.get("schedule", {}),
        database=db,
    )
