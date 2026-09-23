"""YouTube Music taste import via ytmusicapi (optional dependency).

YouTube Music has no official public API; ytmusicapi reuses your own
browser session (browser.json) to read your own library — no scraping
of third parties.
"""

from __future__ import annotations

from .. import config
from ..models import ArtistTaste


def available() -> bool:
    if not config.YTMUSIC_AUTH_FILE:
        return False
    try:
        import ytmusicapi  # noqa: F401
    except ImportError:
        return False
    return True


def fetch_taste() -> list[ArtistTaste]:
    if not available():
        return []
    from ytmusicapi import YTMusic

    yt = YTMusic(config.YTMUSIC_AUTH_FILE)
    artists: list[ArtistTaste] = []
    library = yt.get_library_subscriptions(limit=50) or []
    for rank, item in enumerate(library):
        name = item.get("artist") or item.get("title")
        if not name:
            continue
        aff = 1.0 - 0.6 * rank / max(len(library) - 1, 1)
        artists.append(ArtistTaste(name=name, affinity=round(aff, 3), source="ytmusic"))
    return artists
