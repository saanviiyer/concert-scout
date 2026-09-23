"""Spotify taste import via Authorization Code + PKCE (no client secret).

Flow: /connect/spotify redirects to Spotify -> user approves ->
/callback exchanges the code -> we pull top artists and store the
profile in memory. Nothing is persisted to disk.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx

from .. import config
from ..models import ArtistTaste

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"

# state -> code_verifier for in-flight OAuth handshakes
_pending: dict[str, str] = {}


def auth_redirect_url() -> str:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(16)
    _pending[state] = verifier
    return AUTH_URL + "?" + urlencode(
        {
            "client_id": config.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": config.SPOTIFY_REDIRECT_URI,
            "scope": "user-top-read user-follow-read",
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
        }
    )


async def fetch_taste(code: str, state: str) -> list[ArtistTaste]:
    verifier = _pending.pop(state, None)
    if verifier is None:
        raise ValueError("Unknown OAuth state — restart the Spotify connect flow.")

    async with httpx.AsyncClient() as client:
        tok = await client.post(
            TOKEN_URL,
            data={
                "client_id": config.SPOTIFY_CLIENT_ID,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.SPOTIFY_REDIRECT_URI,
                "code_verifier": verifier,
            },
            timeout=15,
        )
        tok.raise_for_status()
        access = tok.json()["access_token"]
        headers = {"Authorization": f"Bearer {access}"}

        artists: dict[str, ArtistTaste] = {}
        # Medium-term top artists carry the strongest signal; long-term fills in.
        for time_range, base_aff in (("medium_term", 1.0), ("long_term", 0.75)):
            resp = await client.get(
                f"{API}/me/top/artists",
                params={"limit": 30, "time_range": time_range},
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            items = resp.json().get("items", [])
            for rank, item in enumerate(items):
                name = item["name"]
                # Rank-weighted affinity: #1 -> base, #30 -> ~0.35*base
                aff = base_aff * (1.0 - 0.65 * rank / max(len(items) - 1, 1))
                prev = artists.get(name)
                if prev is None or aff > prev.affinity:
                    artists[name] = ArtistTaste(
                        name=name,
                        affinity=round(aff, 3),
                        source="spotify",
                        genres=item.get("genres", [])[:4],
                    )
        return sorted(artists.values(), key=lambda a: -a.affinity)
