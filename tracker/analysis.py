"""Day-over-day deltas, deal tagging and value ranking."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from statistics import median

from . import db
from .config import Config, Destination
from .models import Quote


@dataclass
class DestReport:
    dest: Destination
    status: str = "ok"
    message: str = ""
    options: list[Quote] = field(default_factory=list)
    history: list[tuple[date, float]] = field(default_factory=list)   # includes today
    prev_date: date | None = None
    prev_price: float | None = None
    delta: float | None = None          # today - previous (negative = cheaper)
    hist_min: float | None = None       # over days before today
    hist_median: float | None = None
    pct_vs_median: float | None = None  # negative = below median
    deal: str = ""                      # "", "good", "great"
    deal_reason: str = ""
    trip_cost: float | None = None      # per pax: flight + ground cost for the stay
    value_score: float | None = None
    is_cheapest: bool = False
    value_rank: int | None = None
    tier: str = ""                      # value tier css class, set by the dashboard
    price_rank: int = 0                 # 1 = cheapest priced destination today
    ranked: int = 0

    @property
    def best(self) -> Quote | None:
        return self.options[0] if self.options else None

    @property
    def price(self) -> float | None:
        return self.best.total_per_pax if self.best else None


@dataclass
class DailyReport:
    run_date: date
    rows: list[DestReport]              # priced rows first (cheapest first), then unavailable
    fetched_at: str = ""                # ISO time the prices were fetched

    @property
    def priced(self) -> list[DestReport]:
        return [r for r in self.rows if r.best]

    @property
    def cheapest(self) -> DestReport | None:
        return self.priced[0] if self.priced else None

    @property
    def by_value(self) -> list[DestReport]:
        return sorted(self.priced, key=lambda r: r.value_rank)


def tag_deal(price: float, prior: list[float], cfg: dict) -> tuple[str, str, float | None]:
    """Compare today's price with earlier tracked prices for the same destination."""
    if len(prior) < int(cfg.get("min_history_days", 3)):
        return "", "", None
    med = median(prior)
    pct = (price - med) / med * 100
    if price < min(prior):
        return "great", f"lowest in {len(prior) + 1} days tracked", pct
    if pct <= -float(cfg.get("great_pct_below_median", 12)):
        return "great", f"{-pct:.0f}% below typical", pct
    if pct <= -float(cfg.get("good_pct_below_median", 5)):
        return "good", f"{-pct:.0f}% below typical", pct
    return "", "", pct


def build_report(cfg: Config, con, run_date: date | None = None) -> DailyReport | None:
    run_date = run_date or db.latest_date(con)
    if run_date is None:
        return None
    rows = []
    for d in cfg.destinations:
        status, message = db.status_on(con, run_date, d.code)
        r = DestReport(dest=d, status=status, message=message,
                       options=db.quotes_on(con, run_date, d.code),
                       history=db.history(con, d.code, run_date))
        prior = [(dt, p) for dt, p in r.history if dt < run_date]
        if r.best:
            if prior:
                r.prev_date, r.prev_price = prior[-1]
                r.delta = round(r.price - r.prev_price, 2)
                prices = [p for _, p in prior]
                r.hist_min, r.hist_median = min(prices), median(prices)
            r.deal, r.deal_reason, r.pct_vs_median = tag_deal(r.price, [p for _, p in prior], cfg.deals)
            r.trip_cost = r.price + d.daily_ground_cost * cfg.trip.nights
            r.value_score = round(d.experience_score / r.trip_cost * 1000, 2)
        rows.append(r)

    priced = sorted((r for r in rows if r.best), key=lambda r: r.price)
    if priced:
        priced[0].is_cheapest = True
    for i, r in enumerate(sorted(priced, key=lambda r: -r.value_score), 1):
        r.value_rank = i
    return DailyReport(run_date, priced + [r for r in rows if not r.best], db.fetched_at(con, run_date))


def recommendation(rep: DailyReport, cfg: Config) -> str:
    """One-paragraph plain-text summary."""
    if not rep.priced:
        return "No qualifying non-stop itineraries were found today."
    s, n = cfg.trip.symbol, max(cfg.trip.pax)
    top = rep.by_value[0]
    parts = [f"Best value: {top.dest.name} - {s}{top.price:,.0f}/pax flights, about "
             f"{s}{top.trip_cost:,.0f}/pax all-in for {cfg.trip.nights} nights."]
    c = rep.cheapest
    if c is not top:
        parts.append(f"Cheapest flights: {c.dest.name} at {s}{c.price:,.0f}/pax.")
    by_country: dict[str, DestReport] = {}
    for r in rep.priced:                       # rep.priced is cheapest-first
        by_country.setdefault(r.dest.country, r)
    if len(by_country) == 2:
        lo, hi = sorted(by_country.values(), key=lambda r: r.price)
        parts.append(f"Cheapest in {hi.dest.country} is {hi.dest.name}, {s}{(hi.price - lo.price) * n:,.0f} more "
                     f"for {n} pax than {lo.dest.name} in {lo.dest.country}.")
    missing = [r.dest.name for r in rep.rows if not r.best]
    if missing:
        parts.append(f"No qualifying non-stop found for {', '.join(missing)}.")
    deals = [r.dest.name for r in rep.priced if r.deal == "great"]
    if deals:
        parts.append(f"Great price right now: {', '.join(deals)}.")
    return " ".join(parts)
