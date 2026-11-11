"""CLI:  python -m tracker <command>

  run        fetch live prices from every configured source, store them, print/send the report,
             write the dashboard and offers.json
  report     re-render the latest stored snapshot (no fetching)
  serve      serve the live dashboard over HTTP (its Refresh Fares button runs a real fetch)
  schedule   stay running and do `run --send` every day at the configured time
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time as _time
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from . import db, telegram
from .aggregate import fetch_all
from .analysis import build_report
from .config import ROOT, load_config
from .dashboard import render_dashboard, render_fragment
from .logos import fetch_missing
from .providers.base import live_sources
from .report import render_telegram


def _today(cfg) -> date:
    return datetime.now(ZoneInfo(cfg.schedule.get("timezone", "Asia/Singapore"))).date()


def _latest_json(rep) -> str:
    return json.dumps({"run_date": rep.run_date.isoformat(), "generated": rep.fetched_at} if rep else {})


def fetch_and_save(cfg, sources=None):
    """Query every source for every destination and store today's snapshot."""
    sources = sources or live_sources(cfg)
    results, status = fetch_all(cfg, sources)
    for r in results:
        print(f"  {r.dest}: {r.status} ({len(r.quotes)} offers) {r.message}", file=sys.stderr)
    fetch_missing((leg.airline, leg.flight_number) for r in results for q in r.quotes
                  for leg in (q.outbound, q.inbound))          # best effort; initials are the fallback
    db.save(db.connect(cfg.database), _today(cfg), results, status)
    return results


def _publish(cfg, con, args) -> int:
    rep = build_report(cfg, con)
    out = Path(args.html)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_dashboard(rep, cfg), encoding="utf-8")
    (out.parent / "latest.json").write_text(_latest_json(rep))      # the Refresh button compares against this
    offers = db.offers(con, rep.run_date, max(cfg.trip.pax)) if rep else []
    (out.parent / "offers.json").write_text(json.dumps(offers, indent=1))
    if args.fragment:
        frag = Path(args.fragment)
        frag.write_text(render_fragment(rep, cfg), encoding="utf-8")
        (frag.parent / "latest.json").write_text(_latest_json(rep))
    if rep is None:
        print("No live fares stored yet - run `python -m tracker run`.", file=sys.stderr)
        return 1
    text = render_telegram(rep, cfg, os.environ.get("DASHBOARD_URL", ""))
    if args.send:
        telegram.send(text)
        print(f"Sent to Telegram. Dashboard: {out}")
    else:
        print(text)
        print(f"\n[dashboard written to {out}]", file=sys.stderr)
    return 0


def cmd_run(cfg, args) -> int:
    results = fetch_and_save(cfg)
    rc = _publish(cfg, db.connect(cfg.database), args)
    return 2 if all(r.status == "error" for r in results) else rc


def cmd_report(cfg, args) -> int:
    return _publish(cfg, db.connect(cfg.database), args)


def cmd_serve(cfg, args) -> int:
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str, code: int = 200):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            con = db.connect(cfg.database)
            rep = build_report(cfg, con)
            if self.path.startswith("/latest.json"):
                return self._send(_latest_json(rep).encode(), "application/json")
            if self.path.startswith("/offers.json"):
                rows = db.offers(con, rep.run_date, max(cfg.trip.pax)) if rep else []
                return self._send(json.dumps(rows).encode(), "application/json")
            self._send(render_dashboard(rep, cfg).encode(), "text/html; charset=utf-8")

        def do_POST(self):
            """The page's Refresh Fares button: fetch fresh prices now."""
            if not self.path.startswith("/api/refresh"):
                return self._send(b"{}", "application/json", 404)
            if not lock.acquire(blocking=False):
                return self._send(b'{"status":"busy"}', "application/json", 429)
            try:
                results = fetch_and_save(cfg)
                ok = any(r.status != "error" for r in results)
                self._send(json.dumps({"status": "ok" if ok else "error"}).encode(), "application/json",
                           200 if ok else 502)
            except Exception as e:
                self._send(json.dumps({"status": "error", "message": str(e)}).encode(), "application/json", 500)
            finally:
                lock.release()

        def log_message(self, *a):
            pass

    print(f"Dashboard on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), H).serve_forever()
    return 0


def cmd_schedule(cfg, args) -> int:
    tz = ZoneInfo(cfg.schedule.get("timezone", "Asia/Singapore"))
    hh, mm = map(int, str(cfg.schedule.get("time", "08:00")).split(":"))
    args.send = True
    while True:
        now = datetime.now(tz)
        nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if nxt <= now:
            nxt += timedelta(days=1)
        print(f"Next run at {nxt:%Y-%m-%d %H:%M %Z}", file=sys.stderr)
        _time.sleep((nxt - now).total_seconds())
        try:
            cmd_run(cfg, args)
        except Exception as e:
            print(f"Run failed: {e}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(prog="tracker", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--send", action="store_true", help="send the report to Telegram")
        p.add_argument("--html", default=str(ROOT / "public" / "index.html"), help="dashboard output path")
        p.add_argument("--fragment", default="", help="also write the page without <html>/<body> wrappers")

    common(sub.add_parser("run"))
    common(sub.add_parser("report"))
    p = sub.add_parser("serve"); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8000)
    common(sub.add_parser("schedule"))

    args = ap.parse_args()
    cfg = load_config(args.config)
    try:
        return {"run": cmd_run, "report": cmd_report, "serve": cmd_serve, "schedule": cmd_schedule}[args.cmd](cfg, args)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
