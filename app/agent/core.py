"""ConcertScoutAgent — a self-contained, explainable agent loop.

No LLM involved: every decision is made by inspectable heuristics, and
each stage appends to a trace the UI renders, so you can always see
*why* the agent recommended what it did.

Stages: PERCEIVE (taste) -> PLAN (search strategy) -> ACT (scout
providers) -> OPTIMIZE (score price/date/seats) -> EXPLAIN (reasons).
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import config
from ..models import (
    AgentStep,
    ArtistTaste,
    RecommendRequest,
    RecommendResponse,
)
from . import explain, optimize, scout


class ConcertScoutAgent:
    def __init__(self, req: RecommendRequest):
        self.req = req
        self.trace: list[AgentStep] = []

    def _step(self, stage: str, summary: str, detail: list[str] | None = None):
        self.trace.append(AgentStep(stage=stage, summary=summary, detail=detail or []))

    async def run(self) -> RecommendResponse:
        req = self.req

        # --- PERCEIVE: normalize the taste profile ---
        artists = self._perceive(req.artists)

        # --- PLAN: resolve the search window and strategy ---
        start, end = self._plan(artists)

        # --- ACT: scout events across providers ---
        events, scout_log = await scout.scout_events(artists, req.city, start, end)
        self._step(
            "act",
            f"Found {len(events)} candidate concerts.",
            scout_log,
        )

        # --- OPTIMIZE: score and rank ---
        affinities = {a.name.lower(): a.affinity for a in artists}
        recs, opt_log = optimize.optimize(events, affinities, req)
        recs = recs[: req.max_results]
        self._step(
            "optimize",
            f"Scored {len(events)} events on taste (40%), price (30%), date (15%), seats (15%); kept top {len(recs)}.",
            opt_log,
        )

        # --- EXPLAIN ---
        for rec in recs:
            rec.reasons = explain.explain(rec, req.budget)
        if recs:
            top = recs[0].event
            self._step("explain", f"Top pick: {top.artist} at {top.venue} on {top.date}.")
        else:
            self._step("explain", "No events matched — try a wider date range, higher budget, or more artists.")

        return RecommendResponse(
            recommendations=recs,
            trace=self.trace,
            provider_status=config.provider_status(),
            considered_events=len(events),
        )

    def _perceive(self, artists: list[ArtistTaste]) -> list[ArtistTaste]:
        # Dedupe by name, keep highest affinity, cap the fan-out.
        seen: dict[str, ArtistTaste] = {}
        for a in artists:
            key = a.name.strip().lower()
            if not key:
                continue
            if key not in seen or a.affinity > seen[key].affinity:
                seen[key] = a
        ranked = sorted(seen.values(), key=lambda a: -a.affinity)[:25]
        sources = sorted({a.source for a in ranked}) or ["none"]
        self._step(
            "perceive",
            f"Taste profile: {len(ranked)} artists from {', '.join(sources)}.",
            [f"{a.name} (affinity {a.affinity:.2f})" for a in ranked[:8]],
        )
        return ranked

    def _plan(self, artists: list[ArtistTaste]) -> tuple[str, str]:
        req = self.req
        start = req.start_date or date.today().isoformat()
        end = req.end_date or (date.fromisoformat(start) + timedelta(days=90)).isoformat()
        status = config.provider_status()
        live = [p for p in ("ticketmaster", "seatgeek") if status[p]]
        strategy = f"live providers: {', '.join(live)}" if live else "demo provider (no API keys set)"
        self._step(
            "plan",
            f"Search {len(artists)} artists in {req.city or 'any city'}, {start} → {end}, budget ${req.budget:.0f}.",
            [
                f"Using {strategy}.",
                f"Seat preference: {req.seat_pref:.1f} (0 = cheapest, 1 = best seats).",
                f"Weekend preference: {'on' if req.weekend_pref else 'off'}.",
            ],
        )
        return start, end
