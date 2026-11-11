"""Normalise fares so every price includes one checked bag per person."""
from __future__ import annotations


def bag_policy(airline: str, cfg: dict) -> tuple[bool, float, str]:
    """Return (included_in_fare, round_trip_addon_per_pax, note)."""
    name = airline.lower()
    for a in cfg.get("included", []):
        if a.lower() in name:
            return True, 0.0, "checked bag included in fare"
    for a, fee in cfg.get("addon", {}).items():
        if a.lower() in name:
            return False, float(fee), f"incl. est. {fee:.0f} checked-bag add-on"
    fee = float(cfg.get("default_addon", 80))
    return False, fee, f"incl. est. {fee:.0f} bag add-on - verify baggage"


def apply_baggage(quote, cfg: dict):
    """Use the stricter policy of the two carriers on the itinerary."""
    results = [bag_policy(a, cfg) for a in {quote.outbound.airline, quote.inbound.airline}]
    if all(r[0] for r in results):
        quote.bag_included, quote.bag_fee_per_pax, quote.bag_note = results[0]
    else:
        worst = max(results, key=lambda r: r[1])
        # mixed carriers: half the round-trip fee for each paid direction
        fee = worst[1] if len(results) == 1 else sum(r[1] for r in results) / 2
        quote.bag_included, quote.bag_fee_per_pax, quote.bag_note = False, round(fee, 2), worst[2]
    return quote
