"""Run every live source for every destination concurrently and merge the results.

A source that errors or times out for a destination is recorded and skipped;
whatever the other sources returned is still stored and shown.
"""
from __future__ import annotations

import asyncio

from .models import FetchResult, Quote

# Platforms the tracker reports coverage for: label -> lowercase fragments matched against
# the seller and airline names in the day's offers.
PLATFORMS = {
    "Google Flights": ["google flights"], "Skyscanner": ["skyscanner"], "Trip.com": ["trip.com"],
    "Agoda": ["agoda"], "Traveloka": ["traveloka"], "Kayak": ["kayak"],
    "Scoot": ["scoot"], "T'way Air": ["t'way", "tway"], "Singapore Airlines": ["singapore airlines"],
    "Cathay Pacific": ["cathay"], "Korean Air": ["korean air"],
}


async def _one(source, dest_code: str, sem: asyncio.Semaphore, timeout: float) -> FetchResult:
    async with sem:
        try:
            r = await asyncio.wait_for(asyncio.to_thread(source.fetch, dest_code), timeout)
        except asyncio.TimeoutError:
            r = FetchResult(dest_code, status="error", message=f"Timed out after {timeout:.0f}s")
        except Exception as e:                         # one failing source/route must not sink the run
            r = FetchResult(dest_code, status="error", message=f"{type(e).__name__}: {e}")
    r.source = source.name
    return r


def merge(dest_code: str, parts: list[FetchResult], keep: int) -> FetchResult:
    """Combine one destination's results from all sources into a single ranked result."""
    best: dict[tuple, Quote] = {}
    for p in parts:
        for q in p.quotes:
            key = (q.outbound.flight_number, q.inbound.flight_number, q.seller.lower())
            if key not in best or q.total_per_pax < best[key].total_per_pax:
                best[key] = q
    quotes = sorted(best.values(), key=lambda q: q.total_per_pax)
    # at most one row per (itinerary, seller); show the cheapest sellers, cheapest first
    if quotes:
        return FetchResult(dest_code, quotes=quotes[:keep], source="+".join(sorted({q.source for q in quotes})))
    if parts and all(p.status == "error" for p in parts):
        return FetchResult(dest_code, status="error", message="; ".join(f"{p.source}: {p.message}" for p in parts))
    msg = next((p.message for p in parts if p.status == "none"), "No qualifying non-stop flight")
    return FetchResult(dest_code, status="none", message=msg)


async def _run(cfg, sources) -> tuple[list[FetchResult], list[tuple]]:
    pcfg = cfg.provider
    timeout = float(pcfg.get("timeout_seconds", 180))
    tasks, index = [], []
    for s in sources:
        sem = asyncio.Semaphore(int(pcfg.get("concurrency", 3)))      # per-source rate limit
        for d in cfg.destinations:
            tasks.append(_one(s, d.code, sem, timeout))
            index.append(d.code)
    done = await asyncio.gather(*tasks)
    by_dest: dict[str, list[FetchResult]] = {d.code: [] for d in cfg.destinations}
    for code, r in zip(index, done):
        by_dest[code].append(r)
    keep = int(pcfg.get("options_per_destination", 4))
    merged = [merge(code, parts, keep) for code, parts in by_dest.items()]
    status = [(r.source, r.dest, r.status, r.message) for r in done]
    return merged, status


def fetch_all(cfg, sources) -> tuple[list[FetchResult], list[tuple]]:
    """Returns (one merged FetchResult per destination, per-source status rows)."""
    return asyncio.run(_run(cfg, sources))


def coverage(quotes: list[Quote]) -> dict[str, bool]:
    """Which named platforms contributed a price or operate a flight in today's offers."""
    seen = " | ".join(f"{q.seller} {q.airline}".lower() for q in quotes)
    return {label: any(f in seen for f in frags) for label, frags in PLATFORMS.items()}
