"""Turns a scored recommendation into human-readable reasons."""

from __future__ import annotations

from datetime import date

from ..models import Recommendation


def explain(rec: Recommendation, budget: float) -> list[str]:
    ev, s = rec.event, rec.score
    reasons: list[str] = []

    if s.affinity >= 0.75:
        reasons.append(f"{ev.artist} is one of your top artists.")
    elif s.affinity >= 0.5:
        reasons.append(f"You listen to {ev.artist} regularly.")

    if ev.min_price is not None:
        if ev.min_price <= budget * 0.5:
            reasons.append(f"Tickets from ${ev.min_price:.0f} — well under your ${budget:.0f} budget.")
        elif ev.min_price <= budget:
            reasons.append(f"Tickets from ${ev.min_price:.0f}, inside your budget.")
        else:
            reasons.append(f"Floor price ${ev.min_price:.0f} is over your ${budget:.0f} budget.")

    if rec.cheapest_of_run and len(rec.run_dates) > 1:
        reasons.append(
            f"Cheapest of {len(rec.run_dates)} nights in {ev.city} — "
            f"other dates: {', '.join(d for d in rec.run_dates if d != ev.date)}."
        )

    try:
        if date.fromisoformat(ev.date).weekday() >= 4:
            reasons.append("Falls on a weekend (Fri–Sun).")
    except ValueError:
        pass

    if rec.picked_tier is not None:
        t = rec.picked_tier
        reasons.append(f"Best seat-for-price tier: {t.name} at ${t.price:.0f}.")

    if ev.also_on:
        alt = ev.also_on[0]
        alt_price = f" from ${alt['min_price']:.0f}" if alt.get("min_price") else ""
        reasons.append(f"Also sold on {alt['provider']}{alt_price} — compare before buying.")

    if ev.listing_count is not None and ev.listing_count < 60:
        reasons.append(f"Only ~{ev.listing_count} listings left.")

    return reasons
