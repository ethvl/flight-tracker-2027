"""Source interface + the timing rules every result must pass."""
from __future__ import annotations

from datetime import datetime

from ..models import FetchResult, Leg


class Provider:
    """One live data source. `fetch` returns qualifying round trips for a destination."""
    name = "base"
    label = "Base"

    def __init__(self, cfg):
        self.cfg = cfg

    def fetch(self, dest_code: str) -> FetchResult:   # pragma: no cover - interface
        raise NotImplementedError


def outbound_ok(leg: Leg, trip) -> bool:
    """Lands at the destination on the departure date, no later than the cut-off."""
    limit = datetime.combine(trip.depart_date, trip.outbound_arrive_by)
    return leg.depart_time.date() == trip.depart_date and leg.arrive_time <= limit


def inbound_ok(leg: Leg, trip) -> bool:
    """Lands back at the origin on the return date, no later than the cut-off."""
    limit = datetime.combine(trip.return_date, trip.return_arrive_by)
    return leg.arrive_time.date() == trip.return_date and leg.arrive_time <= limit


def live_sources(cfg) -> list[Provider]:
    """Every source that has credentials configured. Raises if there are none."""
    from .serpapi import SerpApiProvider
    sources, problems = [], []
    for cls in (SerpApiProvider,):
        try:
            sources.append(cls(cfg))
        except RuntimeError as e:
            problems.append(str(e))
    if not sources:
        raise RuntimeError("No live data source is configured. " + " ".join(problems))
    return sources
