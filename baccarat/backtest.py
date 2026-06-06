"""Backtester: run strategies over many simulated shoes and report results.

For each strategy we track:
- hands bet (how often the strategy actually wagered)
- wins / losses / pushes (ties)
- win rate among decided (non-push) bets
- net units and ROI (return per unit wagered) -- the real bottom line

The "edge" a strategy thinks it has shows up here as ROI. A flat Banker bet
has a known expected ROI of about -1.06%. The honest test of any pattern
system is simple: does its ROI beat that? Spoiler from the math -- it can't,
because it is just betting a subset of the same independent hands.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional

from .engine import Outcome, Shoe, play_hand
from .strategies import NamedStrategy, Bet


# Payout config (kept consistent with calculator.py).
BANKER_COMMISSION = 0.05
TIE_PAYOUT = 8


@dataclass
class StrategyResult:
    name: str
    hands_available: int = 0
    hands_bet: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0  # tie when betting Banker/Player
    net_units: float = 0.0

    @property
    def decided(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        return self.wins / self.decided if self.decided else 0.0

    @property
    def coverage(self) -> float:
        """Fraction of available hands the strategy actually bet on."""
        return self.hands_bet / self.hands_available if self.hands_available else 0.0

    @property
    def roi(self) -> float:
        """Net units returned per unit wagered (the house edge, inverted)."""
        return self.net_units / self.hands_bet if self.hands_bet else 0.0


def _settle(bet: Outcome, result: Outcome) -> float:
    """Return the net unit change for a 1-unit bet given the actual outcome."""
    if result is Outcome.TIE and bet is not Outcome.TIE:
        return 0.0  # push: stake returned
    if bet is result:
        if bet is Outcome.BANKER:
            return 1.0 - BANKER_COMMISSION
        if bet is Outcome.TIE:
            return float(TIE_PAYOUT)
        return 1.0  # Player win
    return -1.0  # loss


def backtest(
    strategies: List[NamedStrategy],
    num_shoes: int = 10_000,
    cut_card_penetration: float = 0.85,
    seed: Optional[int] = None,
) -> List[StrategyResult]:
    """Run every strategy across the same sequence of shoes.

    Args:
        strategies: strategies to evaluate.
        num_shoes: how many full shoes to simulate.
        cut_card_penetration: stop dealing a shoe once this fraction is used
            (real casinos place a cut card; ~85% is typical).
        seed: RNG seed for reproducibility (all strategies see identical hands).
    """
    rng = random.Random(seed)
    results = [StrategyResult(name=s.name) for s in strategies]

    for _ in range(num_shoes):
        shoe = Shoe(rng=rng)
        total_cards = len(shoe)
        stop_at = int(total_cards * (1 - cut_card_penetration))

        history: List[Outcome] = []
        while len(shoe) > max(stop_at, 6):
            result = play_hand(shoe).outcome

            for strat, res in zip(strategies, results):
                res.hands_available += 1
                bet: Bet = strat.decide(history)
                if bet is None:
                    continue
                res.hands_bet += 1
                delta = _settle(bet, result)
                res.net_units += delta
                if result is Outcome.TIE and bet is not Outcome.TIE:
                    res.pushes += 1
                elif delta > 0:
                    res.wins += 1
                else:
                    res.losses += 1

            history.append(result)

    return results


def format_results(results: List[StrategyResult]) -> str:
    """Render a comparison table of backtest results."""
    header = (
        f"{'Strategy':<32}{'Bets':>10}{'Coverage':>10}"
        f"{'Win%':>9}{'Net':>12}{'ROI':>9}"
    )
    lines = [header, "-" * len(header)]
    for r in results:
        lines.append(
            f"{r.name:<32}{r.hands_bet:>10,}{r.coverage:>9.1%}"
            f"{r.win_rate:>9.2%}{r.net_units:>12,.1f}{r.roi:>9.2%}"
        )
    return "\n".join(lines)
