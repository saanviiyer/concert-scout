"""Synthetic event provider so the app works with zero API keys.

Deterministic per artist name, so results are stable across runs.
Generates multi-date "runs" in the requested city so the date/seat
optimizer has something real to chew on.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from random import Random

from ..models import Event, SeatTier

VENUES = [
    ("The Wiltern", 1850),
    ("Greek Theatre", 5900),
    ("Hollywood Bowl", 17500),
    ("The Fonda", 1200),
    ("Kia Forum", 17000),
    ("Shrine Auditorium", 6300),
]

TIER_LAYOUT = [
    # (name, quality, price multiplier vs base)
    ("Upper balcony", 0.15, 1.0),
    ("Lower balcony", 0.35, 1.5),
    ("Rear floor / loge", 0.6, 2.2),
    ("Front floor", 0.85, 3.4),
    ("Pit / front row", 1.0, 5.0),
]


def _rng(artist: str) -> Random:
    seed = int(hashlib.sha256(artist.lower().encode()).hexdigest()[:12], 16)
    return Random(seed)


async def search(
    _client,
    artist: str,
    city: str,
    start_date: str,
    end_date: str,
) -> list[Event]:
    rng = _rng(artist)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    window = max((end - start).days, 1)

    # ~70% of artists are touring in the window; a run is 1-3 nights.
    if rng.random() > 0.7:
        return []
    n_dates = rng.choice([1, 1, 2, 2, 3])
    venue, capacity = rng.choice(VENUES)
    base_price = rng.uniform(35, 140) * (0.8 + capacity / 25000)
    first = start + timedelta(days=rng.randrange(max(window - n_dates, 1)))

    city_name = city or "Los Angeles"
    events: list[Event] = []
    for i in range(n_dates):
        d = first + timedelta(days=i)
        if d > end:
            break
        # Weekends are pricier; later nights of a run are usually cheaper.
        demand = (1.25 if d.weekday() >= 5 else 1.0) * (1.0 - 0.08 * i)
        night_base = base_price * demand * rng.uniform(0.92, 1.08)
        tiers = [
            SeatTier(
                name=name,
                price=round(night_base * mult * rng.uniform(0.95, 1.05), 2),
                quality=quality,
                note=f"~{int(capacity * (0.35 - 0.06 * quality))} seats" if quality < 1 else "limited",
            )
            for name, quality, mult in TIER_LAYOUT
        ]
        events.append(
            Event(
                id=f"demo:{artist.lower().replace(' ', '-')}:{d.isoformat()}",
                provider="demo",
                artist=artist,
                title=f"{artist} — {'Weekend' if d.weekday() >= 5 else 'Night'} show",
                venue=venue,
                city=city_name,
                date=d.isoformat(),
                time=rng.choice(["19:00", "19:30", "20:00"]),
                url="https://www.ticketmaster.com/",
                min_price=min(t.price for t in tiers),
                max_price=max(t.price for t in tiers),
                avg_price=round(sum(t.price for t in tiers) / len(tiers), 2),
                listing_count=rng.randrange(40, 900),
                tiers=tiers,
            )
        )
    return events
