"""Synthetic fares used ONLY by the test suite and local layout checks. Never shipped,
never reachable from the CLI. NOT REAL FARES OR SCHEDULES. Deterministic per (destination, day) so reruns match.
Candidates deliberately include late-arriving flights so the timing filter is exercised.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta

from tracker.baggage import apply_baggage
from tracker.links import build_links
from tracker.models import FetchResult, Leg, Quote
from tracker.providers.base import Provider, inbound_ok, outbound_ok

# dest -> (base fare, airport, flight minutes, tz offset vs SIN in hours,
#          [(airline, code, out dep, in dep, fare mult)])
ROUTES = {
    "TYO": (640, "HND", 415, 1, [("Singapore Airlines", "SQ", "01:05", "00:20", 1.25), ("ANA", "NH", "06:10", "00:55", 1.15),
                                 ("Scoot", "TR", "06:40", "17:30", 0.6), ("Zipair", "ZG", "23:10", "16:40", 0.5)]),
    "KIX": (560, "KIX", 395, 1, [("Singapore Airlines", "SQ", "01:25", "10:55", 1.25), ("Scoot", "TR", "06:15", "07:05", 0.75)]),
    "OKA": (520, "OKA", 310, 1, [("Jetstar", "3K", "02:05", "09:10", 1.0), ("Scoot", "TR", "09:40", "17:30", 0.93)]),
    "SEL": (590, "ICN", 390, 1, [("Singapore Airlines", "SQ", "02:25", "09:00", 1.25), ("Korean Air", "KE", "01:10", "08:35", 1.15),
                                 ("Scoot", "TR", "06:20", "07:40", 0.7), ("T'way Air", "TW", "23:00", "17:20", 0.55)]),
    "CJU": (540, "CJU", 345, 1, [("Scoot", "TR", "09:35", "17:10", 1.0)]),
    "PUS": (610, "PUS", 380, 1, [("Singapore Airlines", "SQ", "01:10", "08:20", 1.0), ("Jeju Air", "7C", "03:30", "22:10", 0.62)]),
}


def _noise(*parts) -> float:
    """Deterministic value in [-1, 1]."""
    h = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(h[:4], "big") / 2**31 - 1


class SyntheticSource(Provider):
    name = "synthetic"
    label = "Synthetic"

    def __init__(self, cfg, today: date | None = None):
        super().__init__(cfg)
        self.today = today or date.today()

    def fetch(self, dest_code: str) -> FetchResult:
        t = self.cfg.trip
        if dest_code not in ROUTES:
            return FetchResult(dest_code, status="none", message="No non-stop service (demo data)")
        base, apt, mins, tz, carriers = ROUTES[dest_code]
        day = self.today.toordinal()
        market = 1 + 0.10 * math.sin(day / 5 + len(dest_code) + ord(dest_code[0])) + 0.05 * _noise(dest_code, day)

        def leg(airline, code, hhmm, d, outbound, n):
            dep = datetime.combine(d, datetime.strptime(hhmm, "%H:%M").time())
            arr = dep + timedelta(minutes=mins, hours=tz if outbound else -tz)
            a, b = (t.origin, apt) if outbound else (apt, t.origin)
            return Leg(airline, f"{code} {n}", a, dep, b, arr, mins)

        quotes = []
        for i, (airline, code, out_dep, in_dep, mult) in enumerate(carriers):
            out = leg(airline, code, out_dep, t.depart_date, True, 500 + i * 12)
            inn = leg(airline, code, in_dep, t.return_date, False, 501 + i * 12)
            if not (outbound_ok(out, t) and inbound_ok(inn, t)):
                continue
            fare = round(base * mult * market * (1 + 0.03 * _noise(airline, dest_code, day)))
            q = Quote(dest=dest_code, outbound=out, inbound=inn, fare_per_pax=float(fare), source=self.name, seller=airline)
            apply_baggage(q, self.cfg.baggage)
            q.links = build_links(t, self.cfg.dest(dest_code), [airline])
            quotes.append(q)
        if not quotes:
            return FetchResult(dest_code, status="none", message=f"No non-stop itinerary lands by {t.outbound_arrive_by:%H:%M} both ways")
        quotes.sort(key=lambda q: q.total_per_pax)
        return FetchResult(dest_code, quotes=quotes[: int(self.cfg.provider.get("options_per_destination", 3))])
