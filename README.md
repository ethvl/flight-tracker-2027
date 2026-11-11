# SIN flight price tracker

Daily comparison of non-stop, bag-inclusive round trips from Singapore for
10–16 May 2027 across six East Asian destinations: Tokyo (NRT/HND), Kyoto
(via Osaka Kansai, KIX), Okinawa (OKA), Seoul (ICN/GMP), Jeju (CJU) and Busan
(PUS). Pushes a Telegram report every morning and publishes a mobile-friendly
dashboard.

## What it does each day

1. Queries every configured live source for all six destinations concurrently
   (non-stop, round trip). There is no demo or sample data anywhere in the app:
   with no source configured the dashboard shows "No live fares yet".
2. Keeps only itineraries that land at the destination by 15:00 on 10 May and
   back in Singapore by 15:00 on 16 May (exact check in code, local times).
3. For the cheapest itinerary per destination, pulls the price each seller
   quotes for it (the airline itself, Trip.com and other agencies).
4. Normalises every fare to include one checked bag (see "Baggage" below).
5. Stores the snapshot in SQLite (`data/prices.db`) and writes `offers.json`
   in one flat schema: destination, airline, flight_number, price_1_pax,
   price_4_pax, departure_time, arrival_time, is_direct, includes_baggage,
   source_platform, booking_link, timestamp.
6. Builds the report (day-over-day change, deal tags, value ranking), sends it
   to Telegram and writes `public/index.html`.

A source that fails or times out for a destination is logged in the
`source_status` table and skipped; the rest still publish.

## Data sources

| Source | How | Status |
|---|---|---|
| Google Flights | SerpAPI `google_flights` (search, return, booking options) | implemented |
| Airlines and agencies (Scoot, Singapore Airlines, Korean Air, T'way, Trip.com, ...) | as sellers inside Google Flights booking options | covered when they sell the itinerary |
| Skyscanner, Kayak, Agoda, Traveloka, direct airline sites | need each company's partner API access | not connected |

The tracker does not scrape sites that block automated access, and has no
proxy rotation or user-agent spoofing. New sources plug in as a `Provider`
subclass in `tracker/providers/` and are picked up by `live_sources()`.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `SERPAPI_KEY` | serpapi.com dashboard |
| `TELEGRAM_BOT_TOKEN` | message @BotFather in Telegram, `/newbot` |
| `TELEGRAM_CHAT_ID` | message your bot once, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `chat.id` (use a group's id to share with travel companions) |

## Commands

```bash
python -m tracker run                # fetch real prices, print the report
python -m tracker run --send         # ...and push it to Telegram
python -m tracker report --send      # resend the latest stored report without fetching
python -m tracker serve --port 8000  # live dashboard
python -m tracker schedule           # stay running, run + send daily at schedule.time
python -m pytest                     # tests
```

## Running it every day

**GitHub Actions (recommended, free, no server).** Push this folder to a private
repo, add `SERPAPI_KEY`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` under
Settings → Secrets and variables → Actions, and enable Pages with source
"GitHub Actions". `.github/workflows/daily.yml` then runs at 08:00 Singapore
time, sends the Telegram report, commits the updated `data/prices.db` and
deploys the dashboard. Set the repo variable `DASHBOARD_URL` to the Pages URL
to get a dashboard link in each message. Note that Pages sites on a private
repo are public unless you are on an Enterprise plan.

**Your own machine or server.** Either `python -m tracker schedule` under
systemd/tmux, or cron: `0 8 * * * cd /path/to/flight-tracker && python -m tracker run --send`.

## Configuration (`config.yaml`)

- `destinations`: add or remove destinations; `airports` may list several (e.g. NRT and HND), `primary: true` adds the "Primary pick" badge. `experience_score` (1–10) and
  `daily_ground_cost` are your own inputs and drive only the value ranking.
- `baggage`: which carriers include a checked bag, and the estimated add-on for those that don't.
- `deals`: thresholds for the Good deal / Great price tags.
- `provider.max_return_lookups`: API calls per destination = 1 + this value.

## How the numbers are produced

**Baggage.** Google Flights has no checked-bag filter. Full-service carriers
are shown as quoted; low-cost carriers get an estimated round-trip bag fee
added so prices are comparable. Each option says which case applies. The fees
are estimates: adjust them in `config.yaml` to the bundle you'd buy.

**4 pax.** The single-adult fare × 4. Airlines sometimes price a group higher
when a fare bucket has fewer than four seats left; the 4-pax booking links
show the real total.

**Deal tags.** Each destination is compared with its own history. From the
fourth day: *Great price* = a new low, or ≥12% under the median; *Good deal* = ≥5% under.

**Value score.** `experience_score ÷ (flight + daily_ground_cost × nights) × 1000`.

**Booking links.** Google Flights, Skyscanner and Kayak links open a search
pre-filled with route, dates, 4 adults and non-stop. Airline links open the
carrier's own site (airlines don't offer stable pre-filled URLs).

**Airline logos.** Logos are stored in `assets/logos/<IATA>.png` and embedded
in the page, so nothing loads from an external host when someone views it. Each
run tries to download logos for any new airline; if that fails, the avatar
falls back to the airline's initials on an approximate brand colour.

**Refresh Fares button.** With `python -m tracker serve`, the button runs a real
fetch (`POST /api/refresh`) and reloads with the new prices. On a static host
(GitHub Pages, a published page) it cannot call the fare API, so it checks
`latest.json` and reloads only if a newer daily snapshot has been published.

**Theme.** Light by default on every device; the sun/moon toggle switches to
dark and remembers the choice in that browser.

## API usage

Default settings use up to 4 SerpAPI searches per destination per run
(6 destinations → up to 24 a run, ~720 a month at one run a day). Lower
`max_return_lookups` or set `seller_prices: 0` to reduce it.

## Layout

```
tracker/providers/   serpapi.py (Google Flights), base.py (source interface, timing rules)
tracker/aggregate.py concurrent multi-source fetch, merge, platform coverage
tracker/baggage.py   checked-bag normalisation
tracker/db.py        SQLite log
tracker/analysis.py  day-over-day, deal tags, value ranking
tracker/report.py    Telegram message      tracker/telegram.py  sender
tracker/dashboard.py HTML dashboard        tracker/__main__.py  CLI
```
