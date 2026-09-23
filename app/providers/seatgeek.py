"""SeatGeek Platform API (official, free client ID)."""

from __future__ import annotations

import httpx

from .. import config
from ..models import Event

BASE = "https://api.seatgeek.com/2/events"


async def search(
    client: httpx.AsyncClient,
    artist: str,
    city: str,
    start_date: str,
    end_date: str,
) -> list[Event]:
    if not config.SEATGEEK_CLIENT_ID:
        return []
    params = {
        "client_id": config.SEATGEEK_CLIENT_ID,
        "q": artist,
        "taxonomies.name": "concert",
        "per_page": 20,
        "datetime_local.gte": start_date,
        "datetime_local.lte": f"{end_date}T23:59",
        "sort": "datetime_local.asc",
    }
    if city:
        params["venue.city"] = city
    try:
        resp = await client.get(BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    events: list[Event] = []
    for ev in data.get("events", []):
        dt = ev.get("datetime_local", "")
        if not dt:
            continue
        venue = ev.get("venue") or {}
        stats = ev.get("stats") or {}
        events.append(
            Event(
                id=f"sg:{ev.get('id', '')}",
                provider="seatgeek",
                artist=artist,
                title=ev.get("title", artist),
                venue=venue.get("name", "Unknown venue"),
                city=venue.get("city", city or "Unknown"),
                date=dt[:10],
                time=dt[11:16] or None,
                url=ev.get("url", ""),
                min_price=stats.get("lowest_price"),
                max_price=stats.get("highest_price"),
                avg_price=stats.get("average_price"),
                listing_count=stats.get("listing_count"),
            )
        )
    return events
