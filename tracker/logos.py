"""Airline avatars: a local logo file when we have one, brand-coloured initials otherwise.

Logos live in assets/logos/<IATA>.png and are embedded into the page as data URIs,
so the dashboard never depends on an external image host at view time.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from html import escape
from pathlib import Path

import requests

from .config import ROOT

LOGO_DIR = ROOT / "assets" / "logos"
GENERIC = {"3K"}          # codes whose downloaded file is a generic placeholder, not the airline's logo
LOGO_URL = "https://www.gstatic.com/flights/airline_logos/70px/{code}.png"

# name fragment -> (IATA code, brand colour, text colour, initials). Colours are approximate.
AIRLINES = {
    "singapore airlines": ("SQ", "#1d2c5b", "#f1c75b", "SQ"),
    "scoot": ("TR", "#ffe900", "#111111", "TR"),
    "jetstar": ("3K", "#ff5115", "#ffffff", "JQ"),
    "korean air": ("KE", "#0b4ea2", "#ffffff", "KE"),
    "asiana": ("OZ", "#6b6e72", "#ffffff", "OZ"),
    "ana": ("NH", "#13448f", "#ffffff", "NH"),
    "japan airlines": ("JL", "#cc0000", "#ffffff", "JL"),
    "jal": ("JL", "#cc0000", "#ffffff", "JL"),
    "zipair": ("ZG", "#1f1f1f", "#ffffff", "ZG"),
    "t'way": ("TW", "#d22c26", "#ffffff", "TW"),
    "jeju air": ("7C", "#ff5000", "#ffffff", "7C"),
    "air busan": ("BX", "#0a4da2", "#ffffff", "BX"),
    "jin air": ("LJ", "#6f2c91", "#ffffff", "LJ"),
    "peach": ("MM", "#d1007f", "#ffffff", "MM"),
}


def lookup(airline: str, flight_number: str = ""):
    """Return (code, bg, fg, initials); unknown carriers fall back to their flight-number prefix."""
    name = airline.lower()
    for key, v in AIRLINES.items():
        if key == "ana" and not (name == "ana" or name.startswith(("ana ", "all nippon"))):
            continue
        if key in name:
            return v
    code = (flight_number.split() or [""])[0][:2].upper()
    initials = code or "".join(w[0] for w in airline.split()[:2]).upper() or "?"
    return code, "#3a3a3c", "#ffffff", initials


@lru_cache(maxsize=None)
def _data_uri(code: str) -> str:
    path = LOGO_DIR / f"{code}.png"
    if not code or code in GENERIC or not path.exists() or path.stat().st_size < 200:
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def avatar(airline: str, flight_number: str = "", size: str = "") -> str:
    code, bg, fg, initials = lookup(airline, flight_number)
    cls = "av" + (f" {size}" if size else "")
    uri = _data_uri(code)
    if uri:
        return f'<span class="{cls} logo"><img src="{uri}" alt="" width="70" height="70"></span>'
    return (f'<span class="{cls}" style="background:{bg};color:{fg}" aria-hidden="true">{escape(initials)}</span>')


def fetch_missing(pairs) -> list[str]:
    """Best-effort download of logos we don't have yet. `pairs` = (airline, flight_number).
    Never raises: a blocked or failed request simply leaves the initials fallback in place."""
    got = []
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    for code in {lookup(a, f)[0] for a, f in pairs}:
        path = LOGO_DIR / f"{code}.png"
        if not code or path.exists():
            continue
        try:
            r = requests.get(LOGO_URL.format(code=code), timeout=8)
            if r.ok and r.content[:8] == b"\x89PNG\r\n\x1a\n":
                path.write_bytes(r.content)
                got.append(code)
        except requests.RequestException:
            pass
    _data_uri.cache_clear()
    return got
