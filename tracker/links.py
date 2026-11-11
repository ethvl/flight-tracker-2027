"""Tappable booking deep-links (pre-filled search for the exact trip)."""
from __future__ import annotations

from urllib.parse import quote

AIRLINE_SITES = {
    "singapore airlines": "https://www.singaporeair.com/",
    "scoot": "https://www.flyscoot.com/",
    "airasia": "https://www.airasia.com/flights",
    "jetstar": "https://www.jetstar.com/sg/en/home",
    "thai airways": "https://www.thaiairways.com/",
    "malaysia airlines": "https://www.malaysiaairlines.com/",
    "batik air": "https://www.batikair.com/",
    "garuda": "https://www.garuda-indonesia.com/",
    "vietnam airlines": "https://www.vietnamairlines.com/",
    "vietjet": "https://www.vietjetair.com/",
    "jeju air": "https://www.jejuair.net/",
    "korean air": "https://www.koreanair.com/",
    "asiana": "https://flyasiana.com/",
    "air busan": "https://www.airbusan.com/",
    "t'way": "https://www.twayair.com/",
    "zipair": "https://www.zipair.net/",
    "jin air": "https://www.jinair.com/",
    "peach": "https://www.flypeach.com/",
    "ana": "https://www.ana.co.jp/en/sg/",
    "japan airlines": "https://www.jal.co.jp/sg/en/",
    "jal": "https://www.jal.co.jp/sg/en/",
    "bangkok airways": "https://www.bangkokair.com/",
}


def google_flights(origin, dest, d1, d2, adults=1) -> str:
    q = (f"Flights to {dest} from {origin} on {d1.isoformat()} through {d2.isoformat()} "
         f"nonstop {adults} adult{'s' if adults > 1 else ''}")
    return "https://www.google.com/travel/flights?hl=en&gl=sg&curr=SGD&q=" + quote(q)


def skyscanner(origin, dest, d1, d2, adults=1) -> str:
    return (f"https://www.skyscanner.com.sg/transport/flights/{origin.lower()}/{dest.lower()}/"
            f"{d1:%y%m%d}/{d2:%y%m%d}/?adultsv2={adults}&cabinclass=economy&rtn=1"
            f"&preferdirects=true&stops=!oneStop,!twoPlusStops")


def kayak(origin, dest, d1, d2, adults=1) -> str:
    return (f"https://www.kayak.sg/flights/{origin}-{dest}/{d1.isoformat()}/{d2.isoformat()}/"
            f"{adults}adults?fs=stops=0&sort=price_a")


def airline_site(airline: str) -> str | None:
    name = airline.lower()
    for key, url in AIRLINE_SITES.items():
        if key in name:
            return url
    return None


def build_links(trip, dest, airlines: list[str], exact_google_url: str | None = None) -> dict:
    """Ordered label -> URL. `dest` is a config Destination.
    Aggregator links are pre-filled for the largest party size."""
    pax = max(trip.pax)
    o, d1, d2 = trip.origin, trip.depart_date, trip.return_date
    links = {
        f"Google Flights ({pax} pax)": google_flights(o, dest.google, d1, d2, pax),
        f"Skyscanner ({pax} pax)": skyscanner(o, dest.skyscanner, d1, d2, pax),
        f"Kayak ({pax} pax)": kayak(o, dest.kayak, d1, d2, pax),
    }
    if exact_google_url:
        links["Google Flights (1 pax, exact search)"] = exact_google_url
    for a in dict.fromkeys(airlines):
        url = airline_site(a)
        if url:
            links[a] = url
    return links
