"""Google Flights via SerpAPI (https://serpapi.com/google-flights-api).

Per destination:
  1. outbound search   -> non-stop outbound flights (price = cheapest round trip using it)
  2. return search     -> with the outbound's `departure_token`: matching returns + final price
  3. booking options   -> with the itinerary's `booking_token`: the price each seller
                          (the airline itself, Trip.com, other agencies) quotes for it
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime

import requests

from ..baggage import apply_baggage
from ..links import build_links
from ..models import FetchResult, Leg, Quote
from .base import Provider, inbound_ok, outbound_ok

ENDPOINT = "https://serpapi.com/search.json"


def _leg(option: dict) -> Leg | None:
    segs = option.get("flights") or []
    if len(segs) != 1:                      # non-stop only
        return None
    s = segs[0]
    fmt = "%Y-%m-%d %H:%M"
    return Leg(
        airline=s.get("airline", "Unknown"),
        flight_number=s.get("flight_number", ""),
        depart_airport=s["departure_airport"]["id"],
        depart_time=datetime.strptime(s["departure_airport"]["time"], fmt),
        arrive_airport=s["arrival_airport"]["id"],
        arrive_time=datetime.strptime(s["arrival_airport"]["time"], fmt),
        duration_min=int(s.get("duration") or option.get("total_duration") or 0),
    )


def _options(data: dict) -> list[dict]:
    return (data.get("best_flights") or []) + (data.get("other_flights") or [])


def _checked_bag_free(baggage: list) -> bool | None:
    """True/False when the seller states the checked-bag terms, None when it doesn't."""
    for line in baggage or []:
        low = str(line).lower()
        if "checked" in low:
            return "free" in low or "included" in low
    return None


class SerpApiProvider(Provider):
    name = "google_flights"
    label = "Google Flights"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.key = os.environ.get("SERPAPI_KEY", "")
        # In a managed cloud session the key can live in the network proxy instead of the process.
        self.via_proxy = os.environ.get("SERPAPI_VIA_PROXY") == "1"
        if not self.key and not self.via_proxy:
            raise RuntimeError("SERPAPI_KEY is not set (see .env.example).")

    def _search(self, dest_code: str, **extra) -> dict:
        t = self.cfg.trip
        params = {
            "engine": "google_flights",
            "departure_id": t.origin,
            "arrival_id": ",".join(self.cfg.dest(dest_code).airports),   # e.g. "NRT,HND"
            "outbound_date": t.depart_date.isoformat(),
            "return_date": t.return_date.isoformat(),
            "type": 1,              # round trip
            "travel_class": 1,      # economy
            "adults": 1,
            "stops": 1,             # non-stop only
            "currency": t.currency,
            "hl": "en",
            "gl": "sg",
            "no_cache": "true",     # always a fresh search, never SerpAPI's cached copy
            # coarse pre-filter on arrival hour; the exact cut-off is enforced in code
            "outbound_times": f"0,23,0,{t.outbound_arrive_by.hour}",
            "return_times": f"0,23,0,{t.return_arrive_by.hour}",
            **extra,
        }
        headers = {}
        if self.key:
            params["api_key"] = self.key
        else:
            headers["Authorization"] = "Bearer proxy-injected"
        last = None
        for attempt in range(4):                      # exponential backoff on throttling / server errors
            try:
                r = requests.get(ENDPOINT, params=params, headers=headers, timeout=90)
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                if r.status_code in (401, 403):
                    raise RuntimeError(f"SerpAPI rejected the credentials (HTTP {r.status_code}): {r.text[:200]}")
                return r.json()
            except (requests.RequestException, ValueError) as e:
                last = e
                time.sleep(2 ** attempt * 2)
        raise RuntimeError(f"SerpAPI request failed after retries: {last}")

    # -- step 3 ---------------------------------------------------------------------------------
    def _seller_quotes(self, base: Quote, booking_token: str) -> list[Quote]:
        """One Quote per seller offering this exact itinerary."""
        data = self._search(base.dest, booking_token=booking_token)
        out = []
        for opt in data.get("booking_options") or []:
            o = opt.get("together")
            if not o or not o.get("price") or not o.get("book_with"):
                continue                               # separate-ticket bookings are skipped
            q = Quote(dest=base.dest, outbound=base.outbound, inbound=base.inbound, fare_per_pax=float(o["price"]),
                      source=self.name, seller=o["book_with"], links=dict(base.links))
            apply_baggage(q, self.cfg.baggage)
            if _checked_bag_free(o.get("baggage_prices")) is True:
                q.bag_included, q.bag_fee_per_pax, q.bag_note = True, 0.0, "checked bag included in fare"
            req = o.get("booking_request") or {}
            if req.get("url"):
                q.booking_url = req["url"] + (("?" + req["post_data"]) if req.get("post_data") else "")
            out.append(q)
        return out

    # -- steps 1 + 2 ----------------------------------------------------------------------------
    def fetch(self, dest_code: str) -> FetchResult:
        t, pcfg = self.cfg.trip, self.cfg.provider
        dest = self.cfg.dest(dest_code)
        data = self._search(dest_code)
        if data.get("error") and not _options(data):
            msg = data["error"]
            status = "none" if re.search(r"returned any results|no results", msg, re.I) else "error"
            return FetchResult(dest_code, status=status, message=msg, source=self.name)

        google_url = (data.get("search_metadata") or {}).get("google_flights_url")
        outbounds = []
        for opt in _options(data):
            leg = _leg(opt)
            if leg and outbound_ok(leg, t) and opt.get("price") and opt.get("departure_token"):
                outbounds.append((opt["price"], leg, opt["departure_token"]))
        outbounds.sort(key=lambda x: x[0])
        if not outbounds:
            return FetchResult(dest_code, status="none", source=self.name,
                               message=f"No non-stop outbound flight landing by {t.outbound_arrive_by:%H:%M}")

        found: list[tuple[Quote, str]] = []
        for _, out_leg, token in outbounds[: int(pcfg.get("max_return_lookups", 2))]:
            for opt in _options(self._search(dest_code, departure_token=token)):
                in_leg = _leg(opt)
                if not (in_leg and inbound_ok(in_leg, t) and opt.get("price")):
                    continue
                q = Quote(dest=dest_code, outbound=out_leg, inbound=in_leg, fare_per_pax=float(opt["price"]),
                          source=self.name, seller="Google Flights")
                apply_baggage(q, self.cfg.baggage)
                q.links = build_links(t, dest, [out_leg.airline, in_leg.airline], google_url)
                found.append((q, opt.get("booking_token", "")))
        if not found:
            return FetchResult(dest_code, status="none", source=self.name,
                               message=f"No non-stop return landing in {t.origin} by {t.return_arrive_by:%H:%M}")

        found.sort(key=lambda x: x[0].total_per_pax)
        quotes = [q for q, _ in found]
        for q, token in found[: int(pcfg.get("seller_prices", 1))]:
            if not token:
                continue
            try:
                quotes += self._seller_quotes(q, token)
            except RuntimeError:
                pass                                   # seller breakdown is a bonus; keep the headline price
        return FetchResult(dest_code, quotes=quotes, source=self.name)
