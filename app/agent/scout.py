"""Event scouting: fan out across providers, then dedupe and merge.

The same physical concert often appears on both Ticketmaster and
SeatGeek; we merge those into one Event that carries both purchase
links and the best (lowest) observed floor price.
"""

from __future__ import annotations

import asyncio

import httpx

from .. import config
from ..models import ArtistTaste, Event
from ..providers import demo, seatgeek, ticketmaster

MAX_CONCURRENCY = 8


def _active_providers() -> list:
    providers = []
    if config.TICKETMASTER_API_KEY:
        providers.append(ticketmaster)
    if config.SEATGEEK_CLIENT_ID:
        providers.append(seatgeek)
    if not providers:
        providers.append(demo)
    return providers


async def scout_events(
    artists: list[ArtistTaste],
    city: str,
    start_date: str,
    end_date: str,
) -> tuple[list[Event], list[str]]:
    """Returns (merged events, log lines for the agent trace)."""
    providers = _active_providers()
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    log: list[str] = []

    async with httpx.AsyncClient() as client:
        async def one(provider, artist: ArtistTaste):
            async with sem:
                return await provider.search(client, artist.name, city, start_date, end_date)

        tasks = [one(p, a) for a in artists for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    raw: list[Event] = []
    for res in results:
        if isinstance(res, Exception):
            log.append(f"provider call failed: {res}")
        else:
            raw.extend(res)

    merged = _merge(raw)
    names = ", ".join(p.__name__.split(".")[-1] for p in providers)
    log.insert(0, f"Queried {names} for {len(artists)} artists; {len(raw)} raw hits, {len(merged)} after merge.")
    return merged, log


def _key(ev: Event) -> tuple:
    return (ev.artist.lower(), ev.date, ev.city.lower())


def _merge(events: list[Event]) -> list[Event]:
    by_key: dict[tuple, Event] = {}
    for ev in events:
        k = _key(ev)
        cur = by_key.get(k)
        if cur is None:
            by_key[k] = ev
            continue
        # Keep the listing with the lower floor price as primary;
        # record the other as an alternative purchase route.
        primary, other = (cur, ev)
        if (ev.min_price or 1e9) < (primary.min_price or 1e9):
            primary, other = ev, cur
            by_key[k] = primary
        primary.also_on = list(cur.also_on) + [
            {"provider": other.provider, "url": other.url, "min_price": other.min_price}
        ]
        primary.min_price = min(
            (p for p in (primary.min_price, other.min_price) if p is not None),
            default=primary.min_price,
        )
        primary.listing_count = primary.listing_count or other.listing_count
        primary.avg_price = primary.avg_price or other.avg_price
    return sorted(by_key.values(), key=lambda e: e.date)
