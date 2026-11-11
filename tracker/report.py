"""Telegram (HTML parse mode) rendering of the daily report."""
from __future__ import annotations

from html import escape

from .analysis import DailyReport, DestReport, recommendation
from .config import Config

DEAL_LABEL = {"great": "🔥 GREAT PRICE", "good": "✅ Good deal"}


def money(cfg: Config, v: float) -> str:
    return f"{cfg.trip.symbol}{v:,.0f}"


def delta_text(cfg: Config, r: DestReport) -> str:
    if r.delta is None:
        return "first day tracked" if len(r.history) <= 1 else "no price yesterday"
    if abs(r.delta) < 0.5:
        return "unchanged vs previous day"
    word, arrow = ("cheaper", "🔻") if r.delta < 0 else ("more expensive", "🔺")
    n = max(cfg.trip.pax)
    return (f"{arrow} {money(cfg, abs(r.delta))} {word} per pax "
            f"({money(cfg, abs(r.delta) * n)} for {n}) vs {r.prev_date:%d %b}")


def leg_text(leg) -> str:
    plus = " +1" if leg.arrive_time.date() > leg.depart_time.date() else ""
    return (f"{leg.flight_number} {leg.depart_airport} {leg.depart_time:%H:%M} → "
            f"{leg.arrive_airport} {leg.arrive_time:%H:%M}{plus}")


def _a(label: str, url: str) -> str:
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def _is_aggregator(label: str) -> bool:
    return label.startswith(("Google Flights", "Skyscanner", "Kayak"))


def _airline_links(q) -> str:
    """Per-option links; falls back to the first aggregator so every option is tappable."""
    own = [_a(l, u) for l, u in q.links.items() if not _is_aggregator(l)]
    if not own and q.links:
        l, u = next(iter(q.links.items()))
        own = [_a(l, u)]
    return " · ".join(own)


def _search_links(q) -> str:
    return " · ".join(_a(l, u) for l, u in q.links.items() if _is_aggregator(l))


def render_telegram(rep: DailyReport, cfg: Config, dashboard_url: str = "") -> str:
    t = cfg.trip
    n = max(t.pax)
    out = [
        f"✈️ <b>Flight tracker · {rep.run_date:%a %d %b %Y}</b>",
        f"{t.origin} return · {t.depart_date:%d %b} – {t.return_date:%d %b %Y} · {t.nights} nights",
        f"Non-stop · checked bag included · land by {t.outbound_arrive_by:%H:%M} both ways · {t.currency}",
        "",
    ]

    c = rep.cheapest
    if c:
        out += [f"🏆 <b>Cheapest: {escape(c.dest.name)} – {money(cfg, c.price)}/pax · "
                f"{money(cfg, c.price * n)} for {n}</b>", ""]

    # --- comparison matrix (monospace) ---
    lines = [f"{'':2}{'Dest':<13}{'1 pax':>7}{f'{n} pax':>8}{'vs prev':>9}"]
    for r in rep.rows:
        mark = "★" if r.is_cheapest else ("•" if r.dest.primary else " ")
        if not r.best:
            lines.append(f"{mark:2}{r.dest.name[:12]:<13}{'constraint unmet':>24}")
            continue
        d = "new" if r.delta is None else ("=" if abs(r.delta) < 0.5 else f"{r.delta:+,.0f}")
        lines.append(f"{mark:2}{r.dest.name[:12]:<13}{r.price:>7,.0f}{r.price * n:>8,.0f}{d:>9}")
    out += ["<b>Price matrix</b> (★ cheapest, • your primary picks)",
            "<pre>" + escape("\n".join(lines)) + "</pre>", ""]

    # --- per-destination detail ---
    for r in rep.rows:
        flag = " ⭐" if r.dest.primary else ""
        head = f"<b>{escape(r.dest.name)} ({escape(r.dest.airport_label)}), {escape(r.dest.country)}</b>{flag}"
        if not r.best:
            out += [head, f"✖️ {escape(r.message or 'No qualifying non-stop flight')}", ""]
            continue
        if r.deal:
            head += f" — {DEAL_LABEL[r.deal]} ({escape(r.deal_reason)})"
        out += [head, delta_text(cfg, r)]
        if r.hist_min is not None:
            out.append(f"Tracked range: low {money(cfg, min(r.hist_min, r.price))} · "
                       f"typical {money(cfg, r.hist_median)}")
        for i, q in enumerate(r.options):
            out += [
                f"{'▶️' if i == 0 else '▫️'} <b>{escape(q.airline)}</b> – "
                f"{money(cfg, q.total_per_pax)}/pax · {money(cfg, q.total_per_pax * n)} for {n}",
                f"   <i>{escape(q.bag_note)}</i>",
                f"   Out {escape(leg_text(q.outbound))}",
                f"   Back {escape(leg_text(q.inbound))}",
                f"   Book: {_airline_links(q)}",
            ]
        out.append(f"🔗 Pre-filled search: {_search_links(r.best)}")
        out.append("")

    # --- recommendation ---
    out.append("📊 <b>Value ranking</b> (experience ÷ flight + ground cost)")
    for r in rep.by_value:
        out.append(f"{r.value_rank}. {escape(r.dest.name)} – score {r.value_score:.1f} · "
                   f"~{money(cfg, r.trip_cost)}/pax all-in")
    out += ["", "💡 " + escape(recommendation(rep, cfg))]
    if dashboard_url:
        out += ["", f'<a href="{escape(dashboard_url, quote=True)}">Open live dashboard</a>']
    return "\n".join(out)
