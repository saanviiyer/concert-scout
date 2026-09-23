# Concert Scout

Concert Scout turns your Spotify or YouTube Music taste into ranked concert ticket recommendations. It gets events from the official Ticketmaster and SeatGeek APIs and optimizes for price, seats and dates. The agent uses no LLM. Every decision comes from heuristics that you can inspect.

## How it works

`ConcertScoutAgent` in `app/agent/core.py` runs five stages. It records a trace of each stage, and the UI shows the trace.

1. Perceive. Normalize the taste profile: remove duplicate artists and weight each artist by rank. Taste comes from Spotify top artists, the YT Music library, or manual entry.
2. Plan. Set the search window, city and budget, and check which providers are live.
3. Act. Query Ticketmaster Discovery and the SeatGeek Platform API for each artist, in parallel (async). If both providers sell the same show, merge them into one event with both purchase links and the lower floor price.
4. Optimize. Score each event with `0.40·taste + 0.30·price_value + 0.15·date_fit + 0.15·seat_value`. For multi-night runs (same artist and city), compare each night and flag the cheapest. A seat-vs-price slider picks the best seating tier under budget.
5. Explain. Give plain-English reasons for each pick: why this show, why this night, why this tier, and where it costs less.

The app does no scraping. Event and price data come from the official developer APIs of the providers. Taste comes from Spotify OAuth (PKCE) or from your own YT Music session through `ytmusicapi`.

## Run it

```bash
git clone https://github.com/saanviiyer/concert-scout
cd concert-scout
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py     # http://127.0.0.1:8000 (set PORT=8010 to change)
```

With no keys, the app runs in demo mode. Demo mode uses synthetic events, including multi-night runs and seat tiers.

For YouTube Music import, also run `pip install ytmusicapi`.

## Environment variables

Copy `.env.example` to `.env` and fill in the keys you have. All are optional and free.

| Name | Where to get it | What it adds |
| --- | --- | --- |
| `TICKETMASTER_API_KEY` | developer.ticketmaster.com | Real events and price ranges |
| `SEATGEEK_CLIENT_ID` | seatgeek.com/account/develop | Real events, live lowest and average prices, listing counts |
| `SPOTIFY_CLIENT_ID` | developer.spotify.com/dashboard | One-click taste import. Add the redirect URI `http://127.0.0.1:8000/callback`. |
| `YTMUSIC_AUTH_FILE` | `pip install ytmusicapi`, then `ytmusicapi browser` | Path to `browser.json` for YT Music library import |
| `PORT` | | Server port. Default is 8000. |

The public APIs return price ranges and statistics for each event. They do not return listings for each seat. With live keys, the seat-tier suggestion therefore uses range-based value scoring. Demo mode shows the full tier-level optimization.

YouTube Music has no official API. The `browser.json` auth file holds your own browser session. It is never committed to this repo.

## Layout

```
run.py                  starts the server
app/
  main.py               FastAPI app and routes
  config.py             reads environment variables
  models.py             shared data models
  agent/
    core.py             ConcertScoutAgent and its trace
    scout.py            provider queries, dedupe and merge
    optimize.py         event scoring
    explain.py          plain-English reasons
  providers/            ticketmaster.py, seatgeek.py, demo.py (synthetic events)
  sources/              spotify.py (OAuth PKCE), ytmusic.py
static/                 web UI (index.html, app.js, style.css)
```
