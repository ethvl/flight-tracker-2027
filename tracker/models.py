"""Core data types."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class Leg:
    airline: str
    flight_number: str
    depart_airport: str
    depart_time: datetime      # local time at departure airport
    arrive_airport: str
    arrive_time: datetime      # local time at arrival airport
    duration_min: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["depart_time"] = self.depart_time.isoformat()
        d["arrive_time"] = self.arrive_time.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Leg":
        d = dict(d)
        d["depart_time"] = datetime.fromisoformat(d["depart_time"])
        d["arrive_time"] = datetime.fromisoformat(d["arrive_time"])
        return cls(**d)


@dataclass
class Quote:
    """One round-trip, non-stop itinerary priced per adult."""
    dest: str
    outbound: Leg
    inbound: Leg
    fare_per_pax: float              # as quoted by the source
    bag_fee_per_pax: float = 0.0     # estimated checked-bag add-on (round trip)
    bag_included: bool = False
    bag_note: str = ""
    links: dict[str, str] = field(default_factory=dict)
    source: str = ""                 # data source that returned this price, e.g. "google_flights"
    seller: str = ""                 # who sells the fare at this price (airline or travel agency)
    booking_url: str = ""            # seller's booking link for this exact itinerary, when the source gives one

    @property
    def total_per_pax(self) -> float:
        return round(self.fare_per_pax + self.bag_fee_per_pax, 2)

    @property
    def airline(self) -> str:
        a, b = self.outbound.airline, self.inbound.airline
        return a if a == b else f"{a} / {b}"


@dataclass
class FetchResult:
    dest: str
    quotes: list[Quote] = field(default_factory=list)
    status: str = "ok"               # ok | none | error
    message: str = ""
    source: str = ""
