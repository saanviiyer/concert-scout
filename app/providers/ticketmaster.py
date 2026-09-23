"""Ticketmaster Discovery API (official, free developer key)."""

from __future__ import annotations

import httpx

from .. import config
from ..models import Event

BASE = "https://app.ticketmaster.com/discovery/v2/events.json"


async def search(
    client: httpx.AsyncClient,
    artist: str,
    city: str,
    start_date: str,
    end_date: str,
) -> list[Event]:
    if not config.TICKETMASTER_API_KEY:
        return []
    params = {
        "apikey": config.TICKETMASTER_API_KEY,
        "keyword": artist,
        "classificationName": "music",
        "size": 20,
        "sort": "date,asc",
        "startDateTime": f"{start_date}T00:00:00Z",
        "endDateTime": f"{end_date}T23:59:59Z",
    }
    if city:
        params["city"] = city
    try:
        resp = await client.get(BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []

    events: list[Event] = []
    for ev in data.get("_embedded", {}).get("events", []):
        dates = ev.get("dates", {}).get("start", {})
        date = dates.get("localDate")
        if not date:
            continue
        venues = ev.get("_embedded", {}).get("venues", [{}])
        venue = venues[0] if venues else {}
        prices = ev.get("priceRanges") or []
        price = prices[0] if prices else {}
        events.append(
            Event(
                id=f"tm:{ev.get('id', '')}",
                provider="ticketmaster",
                artist=artist,
                title=ev.get("name", artist),
                venue=venue.get("name", "Unknown venue"),
                city=venue.get("city", {}).get("name", city or "Unknown"),
                date=date,
                time=dates.get("localTime", "")[:5] or None,
                url=ev.get("url", ""),
                min_price=price.get("min"),
                max_price=price.get("max"),
                currency=price.get("currency", "USD"),
            )
        )
    return events
