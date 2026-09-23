# 🎟️ Concert Scout

Your own AI agent (no LLM, no Claude — fully self-contained and explainable) that turns
your Spotify / YouTube Music listening taste into ranked, buy-ready concert ticket
recommendations from **official** Ticketmaster and SeatGeek APIs, optimized for
**price**, **seats**, and **dates**.

## How the agent works

`ConcertScoutAgent` ([app/agent/core.py](app/agent/core.py)) runs a five-stage loop and
records a trace you can inspect in the UI:

1. **Perceive** — normalize the taste profile (dedupe artists, rank-weighted affinities
   from Spotify top artists / YT Music library / manual entry).
2. **Plan** — resolve the search window, city, budget, and which providers are live.
3. **Act** — fan out async queries per artist across Ticketmaster Discovery +
   SeatGeek Platform APIs, then dedupe: the same physical show sold on both is merged
   into one event carrying both purchase links and the lowest floor price.
4. **Optimize** — score every event:
   `0.40·taste + 0.30·price_value + 0.15·date_fit + 0.15·seat_value`.
   Multi-night runs (same artist + city) are compared night-by-night and the cheapest
   night is flagged; a seat-vs-price slider picks the best seating tier under budget.
5. **Explain** — every pick comes with plain-English reasons (why this show, why this
   night, why this tier, where it's cheaper).

No scraping anywhere: event/price data comes from the providers' official developer
APIs, and taste comes from Spotify OAuth (PKCE) or your own YT Music session via
`ytmusicapi`.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py           # http://127.0.0.1:8000  (PORT=8010 to change)
```

Works immediately in **demo mode** (synthetic but realistic events, including
multi-night runs and seat tiers) with zero keys.

## Go live (all keys free)

Copy `.env.example` → `.env` and fill in any of:

| Key | Where | Gives you |
|---|---|---|
| `TICKETMASTER_API_KEY` | developer.ticketmaster.com | real events + price ranges |
| `SEATGEEK_CLIENT_ID` | seatgeek.com/account/develop | real events + live lowest/avg prices, listing counts |
| `SPOTIFY_CLIENT_ID` | developer.spotify.com/dashboard | one-click taste import (add redirect URI `http://127.0.0.1:8000/callback`) |
| `YTMUSIC_AUTH_FILE` | `pip install ytmusicapi` + `ytmusicapi browser` | YT Music library import |

Note: the public APIs return event-level price ranges/stats, not per-seat listings, so
with live keys the seat-tier suggestion falls back to range-based value scoring
(tier-level optimization is fully visible in demo mode).
