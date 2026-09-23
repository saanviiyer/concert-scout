import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "").strip()
SEATGEEK_CLIENT_ID = os.getenv("SEATGEEK_CLIENT_ID", "").strip()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
YTMUSIC_AUTH_FILE = os.getenv("YTMUSIC_AUTH_FILE", "").strip()

APP_HOST = "127.0.0.1"
APP_PORT = int(os.getenv("PORT", "8000"))
SPOTIFY_REDIRECT_URI = f"http://{APP_HOST}:{APP_PORT}/callback"

STATIC_DIR = ROOT / "static"


def provider_status() -> dict:
    return {
        "ticketmaster": bool(TICKETMASTER_API_KEY),
        "seatgeek": bool(SEATGEEK_CLIENT_ID),
        "spotify": bool(SPOTIFY_CLIENT_ID),
        "ytmusic": bool(YTMUSIC_AUTH_FILE and Path(YTMUSIC_AUTH_FILE).exists()),
        "demo_mode": not (TICKETMASTER_API_KEY or SEATGEEK_CLIENT_ID),
    }
