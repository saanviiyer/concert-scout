"""Shared data models for Concert Scout."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ArtistTaste(BaseModel):
    """One artist in the user's taste profile."""

    name: str
    affinity: float = Field(1.0, ge=0.0, le=1.0)  # 0..1, how much the user likes them
    source: str = "manual"  # manual | spotify | ytmusic | demo
    genres: list[str] = []


class TasteProfile(BaseModel):
    artists: list[ArtistTaste] = []
    sources: list[str] = []


class SeatTier(BaseModel):
    """A price tier / seating band for an event."""

    name: str
    price: float
    quality: float = Field(ge=0.0, le=1.0)  # 0 = nosebleeds, 1 = front row
    note: str = ""


class Event(BaseModel):
    id: str
    provider: str  # ticketmaster | seatgeek | demo
    artist: str
    title: str
    venue: str
    city: str
    date: str  # ISO date YYYY-MM-DD
    time: Optional[str] = None  # HH:MM local, if known
    url: str = ""
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    avg_price: Optional[float] = None
    currency: str = "USD"
    listing_count: Optional[int] = None
    tiers: list[SeatTier] = []
    # filled during merge: other providers selling the same event
    also_on: list[dict] = []


class ScoreBreakdown(BaseModel):
    affinity: float
    price_value: float
    date_fit: float
    seat_value: float
    total: float


class Recommendation(BaseModel):
    event: Event
    score: ScoreBreakdown
    picked_tier: Optional[SeatTier] = None
    reasons: list[str] = []
    run_dates: list[str] = []  # all dates for this artist+city run
    cheapest_of_run: bool = False


class AgentStep(BaseModel):
    stage: str
    summary: str
    detail: list[str] = []


class RecommendRequest(BaseModel):
    artists: list[ArtistTaste] = []
    city: str = ""
    start_date: str = ""  # YYYY-MM-DD, empty = today
    end_date: str = ""  # empty = +90 days
    budget: float = 150.0
    seat_pref: float = Field(0.3, ge=0.0, le=1.0)  # 0 = cheapest, 1 = best seats
    weekend_pref: bool = True
    max_results: int = 12


class RecommendResponse(BaseModel):
    recommendations: list[Recommendation]
    trace: list[AgentStep]
    provider_status: dict
    considered_events: int
