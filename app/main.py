"""Concert Scout — FastAPI app wiring the agent to a small web UI."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .agent.core import ConcertScoutAgent
from .models import RecommendRequest, RecommendResponse, TasteProfile
from .sources import spotify, ytmusic

app = FastAPI(title="Concert Scout")

# In-memory taste profile from connected sources (single-user local app).
STATE: dict = {"taste": TasteProfile()}


@app.get("/api/status")
async def status():
    return config.provider_status()


@app.get("/api/taste")
async def taste():
    return STATE["taste"]


@app.post("/api/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    if not req.artists:
        raise HTTPException(400, "Add at least one artist (or connect Spotify / YouTube Music).")
    agent = ConcertScoutAgent(req)
    return await agent.run()


@app.get("/connect/spotify")
async def connect_spotify():
    if not config.SPOTIFY_CLIENT_ID:
        raise HTTPException(400, "Set SPOTIFY_CLIENT_ID in .env first (see .env.example).")
    return RedirectResponse(spotify.auth_redirect_url())


@app.get("/callback")
async def spotify_callback(code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse(f"/?spotify_error={error or 'cancelled'}")
    try:
        artists = await spotify.fetch_taste(code, state)
    except Exception as exc:  # surface OAuth/token failures to the UI
        return RedirectResponse(f"/?spotify_error={type(exc).__name__}")
    profile: TasteProfile = STATE["taste"]
    others = [a for a in profile.artists if a.source != "spotify"]
    profile.artists = artists + others
    profile.sources = sorted({*profile.sources, "spotify"})
    return RedirectResponse("/?spotify=connected")


@app.post("/api/import/ytmusic")
async def import_ytmusic():
    if not ytmusic.available():
        raise HTTPException(
            400,
            "YouTube Music import needs `pip install ytmusicapi` and YTMUSIC_AUTH_FILE in .env "
            "(run `ytmusicapi browser` to create it).",
        )
    artists = ytmusic.fetch_taste()
    profile: TasteProfile = STATE["taste"]
    others = [a for a in profile.artists if a.source != "ytmusic"]
    profile.artists = others + artists
    profile.sources = sorted({*profile.sources, "ytmusic"})
    return {"imported": len(artists)}


@app.get("/")
async def index():
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
