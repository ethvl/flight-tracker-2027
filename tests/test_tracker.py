from datetime import date, datetime, timedelta

from tracker import db
from tracker.analysis import build_report, tag_deal
from tracker.baggage import apply_baggage, bag_policy
from tracker.config import load_config
from tracker.models import FetchResult, Leg, Quote
from tracker.providers.base import inbound_ok, outbound_ok
from tracker.aggregate import coverage, fetch_all, merge
from tracker.dashboard import render_dashboard, sparkline
from tracker.report import render_telegram
from tracker.telegram import split_message

from synthetic import SyntheticSource

CFG = load_config()
T = CFG.trip


def leg(dep, arr, airline="Scoot", a="SIN", b="OKA"):
    return Leg(airline, "TR 1", a, datetime.fromisoformat(dep), b, datetime.fromisoformat(arr), 300)


def quote(dest, fare, airline="Singapore Airlines"):
    q = Quote(dest, leg("2027-05-10T08:00", "2027-05-10T13:00", airline),
              leg("2027-05-16T08:00", "2027-05-16T13:00", airline, dest, "SIN"), fare)
    return apply_baggage(q, CFG.baggage)


def test_timing_cutoffs():
    cut = T.outbound_arrive_by.strftime("%H:%M")
    over = (datetime.combine(T.depart_date, T.outbound_arrive_by) + timedelta(minutes=1)).strftime("%H:%M")
    assert outbound_ok(leg("2027-05-10T08:00", f"2027-05-10T{cut}"), T)
    assert not outbound_ok(leg("2027-05-10T08:00", f"2027-05-10T{over}"), T)
    assert not outbound_ok(leg("2027-05-10T23:00", "2027-05-11T05:00"), T)   # lands next day
    assert not outbound_ok(leg("2027-05-09T23:00", "2027-05-10T05:00"), T)   # leaves a day early
    assert inbound_ok(leg("2027-05-16T01:00", "2027-05-16T06:00"), T)
    assert inbound_ok(leg("2027-05-15T23:30", "2027-05-16T05:00"), T)        # overnight is fine
    rcut = datetime.combine(T.return_date, T.return_arrive_by)
    assert inbound_ok(leg("2027-05-16T12:00", rcut.isoformat()), T)
    assert not inbound_ok(leg("2027-05-16T12:00", (rcut + timedelta(minutes=1)).isoformat()), T)


def test_baggage_normalisation():
    assert CFG.dest("TYO").airports == ["NRT", "HND"] and CFG.dest("KIX").google == "KIX"
    assert bag_policy("Singapore Airlines", CFG.baggage)[0] is True
    inc, fee, _ = bag_policy("Scoot", CFG.baggage)
    assert not inc and fee == 70
    assert bag_policy("Mystery Air", CFG.baggage)[1] == CFG.baggage["default_addon"]
    assert quote("SEL", 200, "Scoot").total_per_pax == 270
    assert quote("SEL", 200).total_per_pax == 200


def test_deal_tagging():
    cfg = CFG.deals
    assert tag_deal(100, [120, 121], cfg)[0] == ""              # not enough history
    assert tag_deal(99, [120, 110, 100, 130], cfg)[0] == "great"   # new low
    assert tag_deal(105, [120, 100, 125, 130], cfg)[0] == "great"  # >=12% under median
    assert tag_deal(114, [120, 100, 125, 130], cfg)[0] == "good"
    assert tag_deal(125, [120, 100, 125, 130], cfg)[0] == ""


def test_report_day_over_day(tmp_path):
    con = db.connect(tmp_path / "t.db")
    d0 = date(2026, 11, 10)
    db.save(con, d0, [FetchResult("OKA", [quote("OKA", 600)]), FetchResult("SEL", [quote("SEL", 250)]),
                      FetchResult("PUS", status="none", message="No non-stop")])
    db.save(con, d0 + timedelta(days=1),
            [FetchResult("OKA", [quote("OKA", 560)]), FetchResult("SEL", [quote("SEL", 265)]),
             FetchResult("PUS", status="none", message="No non-stop")])
    rep = build_report(CFG, con)
    by = {r.dest.code: r for r in rep.rows}
    assert by["OKA"].delta == -40 and by["SEL"].delta == 15
    assert rep.cheapest.dest.code == "SEL" and by["SEL"].is_cheapest
    assert by["PUS"].best is None
    text = render_telegram(rep, CFG)
    assert "S$40 cheaper per pax (S$160 for 4)" in text
    assert "S$15 more expensive per pax" in text
    assert "S$2,240 for 4" in text
    assert all(len(c) <= 4000 for c in split_message(text))


def test_same_day_rerun_replaces_and_errors_keep_data(tmp_path):
    con = db.connect(tmp_path / "t.db")
    d = date(2026, 11, 10)
    db.save(con, d, [FetchResult("OKA", [quote("OKA", 600)])])
    db.save(con, d, [FetchResult("OKA", [quote("OKA", 580)])])
    assert db.history(con, "OKA", d) == [(d, 580)]
    db.save(con, d, [FetchResult("OKA", status="error", message="boom")])
    assert db.history(con, "OKA", d) == [(d, 580)]


def test_synthetic_source_respects_constraints():
    p = SyntheticSource(CFG, today=date(2026, 11, 11))
    for d in CFG.destinations:
        for q in p.fetch(d.code).quotes:
            assert outbound_ok(q.outbound, T) and inbound_ok(q.inbound, T)
            assert q.links and all(u.startswith("https://") for u in q.links.values())


class Broken(SyntheticSource):
    name = "broken"

    def fetch(self, dest_code):
        raise TimeoutError("upstream timed out")


def test_one_failing_source_does_not_sink_the_run(tmp_path):
    good = SyntheticSource(CFG, today=date(2026, 11, 11))
    results, status = fetch_all(CFG, [good, Broken(CFG)])
    assert sum(1 for r in results if r.quotes) >= 4                      # good source still delivered
    assert {s[2] for s in status if s[0] == "broken"} == {"error"}
    con = db.connect(tmp_path / "t.db")
    db.save(con, date(2026, 11, 11), results, status)
    assert db.sources_on(con, date(2026, 11, 11))["broken"] == {"error": len(CFG.destinations)}
    rows = db.offers(con, date(2026, 11, 11))
    need = {"destination", "airline", "flight_number", "price_1_pax", "price_4_pax", "departure_time", "arrival_time",
            "is_direct", "includes_baggage", "source_platform", "booking_link", "timestamp"}
    assert rows and need <= set(rows[0]) and rows[0]["price_4_pax"] == rows[0]["price_1_pax"] * 4
    html = render_dashboard(build_report(CFG, con), CFG)
    assert "Sample" not in html and "Demo" not in html


def test_merge_keeps_cheapest_per_seller_and_all_errors_surface():
    a, b = quote("OKA", 600), quote("OKA", 550)
    a.seller = b.seller = "Scoot"
    c = quote("OKA", 580); c.seller = "Trip.com"
    m = merge("OKA", [FetchResult("OKA", [a, c]), FetchResult("OKA", [b])], keep=5)
    assert [(q.seller, q.fare_per_pax) for q in m.quotes] == [("Scoot", 550), ("Trip.com", 580)]
    cov = coverage(m.quotes)
    assert cov["Scoot"] and cov["Trip.com"] and cov["Singapore Airlines"] and not cov["Agoda"]
    bad = merge("OKA", [FetchResult("OKA", status="error", message="x", source="s1")], keep=5)
    assert bad.status == "error"


def test_empty_state_renders_without_data(tmp_path):
    html = render_dashboard(build_report(CFG, db.connect(tmp_path / "e.db")), CFG)
    assert "No live fares yet" in html


def test_sparkline_matches_history():
    d = date(2026, 11, 10)
    assert sparkline([(d, 700.0)]) == ("", 0)                         # one day: nothing to draw
    svg, n = sparkline([(d, 700.0), (d + timedelta(days=1), 650.0)])
    assert n == 2 and "var(--green)" in svg and "10 Nov S$700" in svg and "11 Nov S$650" in svg
    svg, n = sparkline([(d, 700.0), (d + timedelta(days=1), 700.0)])
    assert "var(--ink2)" in svg and ",20.0" in svg                     # flat line drawn mid-height
    # a missing day keeps its place on the time axis: middle point of 3 days sits at x=120 of 240
    svg, n = sparkline([(d, 700.0), (d + timedelta(days=1), 720.0), (d + timedelta(days=2), 710.0)])
    assert "120.0," in svg and n == 3
    svg, n = sparkline([(d, 700.0), (d + timedelta(days=2), 720.0)])
    assert n == 3 and "var(--red)" in svg
