"""Probability calculator: outcome odds given the cards that remain.

This is the heart of the "card counting" question. Given the exact set of
cards still in the shoe, we estimate:
    P(Banker win), P(Player win), P(Tie)
and from those, the expected value (EV) of each available bet.

We use Monte Carlo here (deal many random hands from the remaining cards and
count outcomes). It is simple, robust, and converges fast. An exact combinatoric
calculator is possible but adds a lot of complexity for negligible practical
gain -- and the headline conclusion (the edge barely moves) is identical.

KEY POINT FOR THE USER:
At the very start of a fresh 8-deck shoe the answer is essentially fixed:
    Banker ~45.86%, Player ~44.62%, Tie ~9.52%.
Removing a handful of cards shifts these by tiny fractions of a percent and
almost never enough to overcome the house edge. This calculator lets you see
that for yourself.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from .engine import Outcome


# Standard payouts.
BANKER_COMMISSION = 0.05  # 5% commission on winning Banker bets
TIE_PAYOUT = 8  # 8-to-1 (some tables pay 9-to-1; configurable below)


@dataclass
class OutcomeProbabilities:
    banker: float
    player: float
    tie: float
    trials: int

    def as_dict(self) -> Dict[str, float]:
        return {"Banker": self.banker, "Player": self.player, "Tie": self.tie}

    def __str__(self) -> str:
        return (
            f"Banker: {self.banker:6.3%}  "
            f"Player: {self.player:6.3%}  "
            f"Tie: {self.tie:6.3%}  "
            f"(n={self.trials:,})"
        )


def _build_value_pool(remaining_value_counts: List[int]) -> List[int]:
    """Turn a list of counts-per-value (index 0..9) into a flat pool of values."""
    pool: List[int] = []
    for value, count in enumerate(remaining_value_counts):
        pool.extend([value] * count)
    return pool


def _total(values: List[int]) -> int:
    return sum(values) % 10


def _resolve_from_values(draw) -> Outcome:
    """Resolve a single coup using a callable `draw()` that yields card *values*.

    Mirrors engine.play_hand but operates directly on point values, which is all
    that matters for the outcome.
    """
    player = [draw(), draw()]
    banker = [draw(), draw()]
    p, b = _total(player), _total(banker)

    if p >= 8 or b >= 8:  # natural
        pass
    else:
        player_third: Optional[int] = None
        if p <= 5:
            player_third = draw()
            player.append(player_third)
            p = _total(player)

        banker_draws: bool
        if player_third is None:
            banker_draws = b <= 5
        elif b <= 2:
            banker_draws = True
        elif b == 3:
            banker_draws = player_third != 8
        elif b == 4:
            banker_draws = 2 <= player_third <= 7
        elif b == 5:
            banker_draws = 4 <= player_third <= 7
        elif b == 6:
            banker_draws = player_third in (6, 7)
        else:
            banker_draws = False

        if banker_draws:
            banker.append(draw())
            b = _total(banker)

    if p > b:
        return Outcome.PLAYER
    if b > p:
        return Outcome.BANKER
    return Outcome.TIE


def probabilities_from_remaining(
    remaining_value_counts: List[int],
    trials: int = 200_000,
    seed: Optional[int] = None,
) -> OutcomeProbabilities:
    """Estimate outcome probabilities by sampling hands from the remaining cards.

    Args:
        remaining_value_counts: counts of values 0..9 still in the shoe
            (e.g. from Shoe.remaining_counts()).
        trials: number of simulated hands.
        seed: optional RNG seed for reproducibility.
    """
    rng = random.Random(seed)
    pool = _build_value_pool(remaining_value_counts)
    if len(pool) < 6:
        raise ValueError("Not enough cards remaining to deal a hand.")

    banker = player = tie = 0

    for _ in range(trials):
        # Sample up to 6 cards without replacement for this coup, then resolve.
        # Drawing one at a time from a shuffled copy is simplest and unbiased.
        rng.shuffle(pool)
        idx = 0

        def draw() -> int:
            nonlocal idx
            v = pool[idx]
            idx += 1
            return v

        result = _resolve_from_values(draw)
        if result is Outcome.BANKER:
            banker += 1
        elif result is Outcome.PLAYER:
            player += 1
        else:
            tie += 1

    return OutcomeProbabilities(
        banker=banker / trials,
        player=player / trials,
        tie=tie / trials,
        trials=trials,
    )


def bet_expected_values(
    probs: OutcomeProbabilities,
    banker_commission: float = BANKER_COMMISSION,
    tie_payout: int = TIE_PAYOUT,
) -> Dict[str, float]:
    """Expected value per 1 unit staked for each bet, given outcome probabilities.

    - Banker: win pays (1 - commission); ties push (stake returned).
    - Player: win pays 1; ties push.
    - Tie:    win pays tie_payout; otherwise lose stake.

    A negative EV means the bet loses money on average (the house edge).
    """
    pb, pp, pt = probs.banker, probs.player, probs.tie

    ev_banker = pb * (1 - banker_commission) + pt * 0 - pp * 1
    ev_player = pp * 1 + pt * 0 - pb * 1
    ev_tie = pt * tie_payout - (pb + pp) * 1

    return {"Banker": ev_banker, "Player": ev_player, "Tie": ev_tie}
