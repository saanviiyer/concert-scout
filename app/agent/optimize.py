"""The optimizer: scores every event on taste, price, date, and seats.

score = 0.40*affinity + 0.30*price_value + 0.15*date_fit + 0.15*seat_value

- affinity     how much the user listens to this artist (taste profile)
- price_value  floor price vs budget, and vs sibling dates of the same run
- date_fit     inside the window, weekend bonus, cheapest night of a run
- seat_value   best tier under budget given the user's seat-vs-price slider
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..models import Event, Recommendation, RecommendRequest, ScoreBreakdown, SeatTier

W_AFFINITY, W_PRICE, W_DATE, W_SEAT = 0.40, 0.30, 0.15, 0.15


def optimize(
    events: list[Event],
    affinities: dict[str, float],
    req: RecommendRequest,
) -> tuple[list[Recommendation], list[str]]:
    log: list[str] = []

    # Group multi-night runs: same artist + city -> compare dates directly.
    runs: dict[tuple, list[Event]] = defaultdict(list)
    for ev in events:
        runs[(ev.artist.lower(), ev.city.lower())].append(ev)

    multi = sum(1 for evs in runs.values() if len(evs) > 1)
    if multi:
        log.append(f"{multi} artist runs have multiple dates — comparing nights for the cheapest one.")

    recs: list[Recommendation] = []
    for run_events in runs.values():
        floor_prices = [e.min_price for e in run_events if e.min_price is not None]
        run_cheapest = min(floor_prices) if floor_prices else None
        run_dates = sorted(e.date for e in run_events)

        for ev in run_events:
            affinity = affinities.get(ev.artist.lower(), 0.5)
            price_value = _price_value(ev, req.budget, run_cheapest)
            date_fit = _date_fit(ev, req, run_cheapest)
            tier, seat_value = _pick_tier(ev, req)
            total = (
                W_AFFINITY * affinity
                + W_PRICE * price_value
                + W_DATE * date_fit
                + W_SEAT * seat_value
            )
            cheapest = (
                len(run_events) > 1
                and ev.min_price is not None
                and ev.min_price == run_cheapest
            )
            recs.append(
                Recommendation(
                    event=ev,
                    score=ScoreBreakdown(
                        affinity=round(affinity, 3),
                        price_value=round(price_value, 3),
                        date_fit=round(date_fit, 3),
                        seat_value=round(seat_value, 3),
                        total=round(total, 3),
                    ),
                    picked_tier=tier,
                    run_dates=run_dates,
                    cheapest_of_run=cheapest,
                )
            )

    recs.sort(key=lambda r: -r.score.total)
    over = [r for r in recs if r.event.min_price and r.event.min_price > req.budget]
    if over:
        log.append(f"{len(over)} events have a floor price above the ${req.budget:.0f} budget — kept but penalized.")
    return recs, log


def _price_value(ev: Event, budget: float, run_cheapest: float | None) -> float:
    if ev.min_price is None:
        return 0.5  # unknown price: neutral
    # Under budget scales 1.0 (free) -> 0.35 (at budget); over decays toward 0.
    if ev.min_price <= budget:
        v = 1.0 - 0.65 * (ev.min_price / budget)
    else:
        v = max(0.0, 0.35 - 0.35 * (ev.min_price - budget) / budget)
    # Small bonus for being the cheapest night of a run.
    if run_cheapest is not None and ev.min_price == run_cheapest:
        v = min(1.0, v + 0.1)
    return v


def _date_fit(ev: Event, req: RecommendRequest, run_cheapest: float | None) -> float:
    v = 0.7
    try:
        d = date.fromisoformat(ev.date)
    except ValueError:
        return v
    if req.weekend_pref and d.weekday() >= 4:  # Fri/Sat/Sun
        v += 0.2
    if run_cheapest is not None and ev.min_price == run_cheapest:
        v += 0.1
    return min(v, 1.0)


def _pick_tier(ev: Event, req: RecommendRequest) -> tuple[SeatTier | None, float]:
    """Choose the tier that best matches the seat-vs-price preference.

    seat_pref=0 wants the cheapest ticket, 1 wants the best seat.
    Tier utility = pref*quality + (1-pref)*(price advantage vs budget).
    """
    if not ev.tiers:
        # No tier data (live APIs give a range, not a seat map):
        # approximate seat value from where the floor sits in the range.
        if ev.min_price is None:
            return None, 0.5
        affordable = ev.min_price <= req.budget
        return None, 0.6 if affordable else 0.25

    best, best_u = None, -1.0
    for t in ev.tiers:
        price_adv = max(0.0, 1.0 - t.price / max(req.budget, 1.0))
        u = req.seat_pref * t.quality + (1 - req.seat_pref) * price_adv
        if t.price > req.budget * 1.15:  # hard-ish budget cap with slack
            u *= 0.3
        if u > best_u:
            best, best_u = t, u
    return best, max(0.0, min(best_u, 1.0))
