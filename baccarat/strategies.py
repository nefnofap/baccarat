"""Betting strategies, expressed as pluggable decision functions.

A strategy looks at the history of past outcomes (the "scorecard") and decides
what to bet on the *next* hand -- or to skip the hand entirely.

This is where we can test the user's idea and the popular "trend" systems
honestly. Every strategy gets fed the same simulated hands by the backtester,
so we compare apples to apples.

IMPORTANT CONTEXT (so the results are not surprising):
Baccarat hands are statistically independent. The probability that the next
hand is a Banker win is ~50.68% (excluding ties) NO MATTER what the previous
hands were -- whether they spelled B-P-B-P, a long streak, or anything else.
So pattern strategies do not change *whether* you win; they only change *which
hands you choose to bet on*. Since every Banker bet has the same negative EV,
selecting a subset of them cannot turn a losing bet into a winning one. The
backtester demonstrates this empirically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from .engine import Outcome


# A Bet is either an Outcome to wager on, or None to skip the hand.
Bet = Optional[Outcome]

# A Strategy maps the list of past outcomes -> the bet for the next hand.
Strategy = Callable[[List[Outcome]], Bet]


@dataclass
class NamedStrategy:
    name: str
    decide: Strategy
    description: str


def _non_tie_history(history: List[Outcome]) -> List[Outcome]:
    """Ties are usually ignored for pattern purposes (a 'push' on B/P bets)."""
    return [o for o in history if o is not Outcome.TIE]


# --------------------------------------------------------------------------- #
# Baseline strategies
# --------------------------------------------------------------------------- #

def always_banker(history: List[Outcome]) -> Bet:
    """Flat-bet Banker every hand. The mathematically lowest-house-edge play."""
    return Outcome.BANKER


def always_player(history: List[Outcome]) -> Bet:
    """Flat-bet Player every hand."""
    return Outcome.PLAYER


# --------------------------------------------------------------------------- #
# The user's strategy: alternating B-P-B-P, then bet Banker.
# --------------------------------------------------------------------------- #

def user_alternating_then_banker(history: List[Outcome]) -> Bet:
    """If the last four non-tie results alternate B,P,B,P -> bet Banker.

    This is the user's described system: when the scoreboard "chops" in a clean
    Banker-Player-Banker-Player pattern, wager Banker on the next coup. Skips
    (no bet) whenever the pattern is not present.
    """
    h = _non_tie_history(history)
    if len(h) < 4:
        return None
    last4 = h[-4:]
    if last4 == [Outcome.BANKER, Outcome.PLAYER, Outcome.BANKER, Outcome.PLAYER]:
        return Outcome.BANKER
    return None


# --------------------------------------------------------------------------- #
# "Follow the streak" / Dragon tail: bet the side currently on a run.
# --------------------------------------------------------------------------- #

def make_follow_streak(min_streak: int = 3) -> Strategy:
    """Bet on the side that has won the last `min_streak` hands in a row.

    Popular "ride the dragon" / "follow the trend" idea: if Banker just won 3+
    in a row, keep betting Banker until the streak breaks.
    """

    def decide(history: List[Outcome]) -> Bet:
        h = _non_tie_history(history)
        if len(h) < min_streak:
            return None
        last = h[-1]
        if all(o is last for o in h[-min_streak:]):
            return last
        return None

    return decide


# --------------------------------------------------------------------------- #
# Chop / zigzag: bet that the result keeps alternating (opposite of last).
# --------------------------------------------------------------------------- #

def make_chop_follow(min_alternations: int = 3) -> Strategy:
    """If the last results have been alternating, bet the chop continues.

    e.g. ...B,P,B  -> bet Player next (expecting the zigzag to hold).
    """

    def decide(history: List[Outcome]) -> Bet:
        h = _non_tie_history(history)
        if len(h) < min_alternations + 1:
            return None
        window = h[-(min_alternations + 1):]
        # Check the window strictly alternates.
        for i in range(1, len(window)):
            if window[i] is window[i - 1]:
                return None
        # Bet the opposite of the most recent result.
        return Outcome.PLAYER if window[-1] is Outcome.BANKER else Outcome.BANKER

    return decide


def default_strategies() -> List[NamedStrategy]:
    """A representative set used by the demo/backtester."""
    return [
        NamedStrategy(
            "Flat Banker (baseline)",
            always_banker,
            "Bet Banker every hand. Lowest house edge (1.06%).",
        ),
        NamedStrategy(
            "User B-P-B-P -> Banker",
            user_alternating_then_banker,
            "Bet Banker only after a B,P,B,P chop.",
        ),
        NamedStrategy(
            "Follow streak (Dragon, 3+)",
            make_follow_streak(3),
            "Ride a run: bet the side that just won 3+ in a row.",
        ),
        NamedStrategy(
            "Chop / zigzag (3+)",
            make_chop_follow(3),
            "Bet the alternating pattern continues.",
        ),
    ]
