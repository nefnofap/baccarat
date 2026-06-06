"""Stateful betting *systems* (selection rule + money management).

The strategies in `strategies.py` only answer "which side?". Real-world systems
also answer "how much?" -- they raise and lower the stake based on wins and
losses (Martingale, progressions) and sometimes skip hands by design (the
Hong Kong Lady "dead hand"). Those need internal state, so they are modeled
here as objects with a small event-driven interface:

    system.reset()                      # new shoe / session
    bet = system.next_bet()             # (side, stake) for the upcoming hand, or None
    system.observe(outcome, won)        # told the actual result + whether our bet won

`won` is True (bet won), False (bet lost), or None (no bet placed, or a tie
pushed the bet). The backtester drives this loop.

THE BIG HONEST CAVEAT
---------------------
No money-management system changes the house edge. Baccarat hands are
independent, so raising your bet after losses (Martingale) does not make a win
more likely -- it only changes the *shape* of your results: many small wins
punctuated by occasional catastrophic losses when a normal losing streak
collides with your bankroll or the table limit. The backtester measures that
risk directly (risk of ruin, max stake reached). Use these to understand the
systems, not to beat the casino -- mathematically, you can't.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .engine import Outcome


# A placed bet is (side, stake) or None to sit out the hand.
PlacedBet = Optional[Tuple[Outcome, float]]


def _opposite(o: Outcome) -> Outcome:
    return Outcome.PLAYER if o is Outcome.BANKER else Outcome.BANKER


class BettingSystem:
    """Base class. Subclasses implement next_bet() and observe()."""

    name: str = "base"
    description: str = ""

    def reset(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def next_bet(self) -> PlacedBet:  # pragma: no cover - overridden
        raise NotImplementedError

    def observe(self, outcome: Outcome, won: Optional[bool]) -> None:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Flat Banker -- the honest baseline.
# --------------------------------------------------------------------------- #

class FlatBanker(BettingSystem):
    name = "Flat Banker"
    description = "Bet 1 unit on Banker every hand. The lowest-edge play."

    def __init__(self, base: float = 1.0) -> None:
        self.base = base

    def reset(self) -> None:
        pass

    def next_bet(self) -> PlacedBet:
        return (Outcome.BANKER, self.base)

    def observe(self, outcome: Outcome, won: Optional[bool]) -> None:
        pass


# --------------------------------------------------------------------------- #
# Martingale on Banker -- double after every loss.
# --------------------------------------------------------------------------- #

class MartingaleBanker(BettingSystem):
    name = "Martingale Banker"
    description = (
        "Bet Banker; double the stake after every loss, reset to base after a win."
    )

    def __init__(self, base: float = 1.0, max_step: int = 10) -> None:
        self.base = base
        self.max_step = max_step  # cap doublings (a stand-in for the table limit)
        self.reset()

    def reset(self) -> None:
        self.step = 0

    def next_bet(self) -> PlacedBet:
        return (Outcome.BANKER, self.base * (2 ** self.step))

    def observe(self, outcome: Outcome, won: Optional[bool]) -> None:
        if won is True:
            self.step = 0
        elif won is False:
            self.step = min(self.step + 1, self.max_step)
        # won is None (a tie pushed the Banker bet): keep the same step.


# --------------------------------------------------------------------------- #
# Paroli on Banker -- a "positive" progression (press wins, not losses).
# --------------------------------------------------------------------------- #

class ParoliBanker(BettingSystem):
    name = "Paroli Banker"
    description = (
        "Bet Banker; double after a win up to 3 in a row, then reset. Safer than "
        "Martingale because losses stay at base stake."
    )

    def __init__(self, base: float = 1.0, target_streak: int = 3) -> None:
        self.base = base
        self.target_streak = target_streak
        self.reset()

    def reset(self) -> None:
        self.win_streak = 0

    def next_bet(self) -> PlacedBet:
        return (Outcome.BANKER, self.base * (2 ** self.win_streak))

    def observe(self, outcome: Outcome, won: Optional[bool]) -> None:
        if won is True:
            self.win_streak += 1
            if self.win_streak >= self.target_streak:
                self.win_streak = 0  # bank the run, start over
        elif won is False:
            self.win_streak = 0
        # tie push: hold.


# --------------------------------------------------------------------------- #
# Hong Kong Lady -- pattern recognition + Martingale.
# --------------------------------------------------------------------------- #

class HongKongLady(BettingSystem):
    """A faithful (best-effort) implementation of the "Hong Kong Lady" system.

    The popular description is internally a bit ambiguous, so this is one
    reasonable, clearly documented reading. Importantly, NO reading changes the
    expected value -- it is still pattern selection plus a Martingale, both of
    which are EV-neutral against an independent game.

    Rules implemented:
      * Ties are ignored entirely (they don't advance any counter).
      * Non-tie hands are grouped into sets of 3; the 4th non-tie hand of each
        block is the "dead hand" and is never bet on (Chinese superstition that
        4 is unlucky). Concretely, non-tie index % 4 == 3 is skipped.
      * The first set of 3 that is NOT all-identical becomes the reference set.
      * Each later set of 3 is compared hand-by-hand to the reference: a match
        records a check, a mismatch records an X.
      * Entry trigger: 3 identical marks in a row (3 checks or 3 X's). Then bet
        the OPPOSITE of the most recent result for up to the next 3 live hands,
        using a Martingale (double after each loss; stop on a win).
      * The Martingale is capped at 3 steps (one betting window). Real players
        often run it uncapped, which is far more dangerous -- see the backtest's
        risk-of-ruin column.
    """

    name = "Hong Kong Lady"
    description = (
        "Pattern (sets of 3, skip the 4th 'dead hand', ignore ties) triggers a "
        "Martingale bet on the opposite side."
    )

    def __init__(self, base: float = 1.0, max_marts: int = 3) -> None:
        self.base = base
        self.max_marts = max_marts
        self.reset()

    def reset(self) -> None:
        self.nt_count = 0           # non-tie hands seen
        self.live: List[Outcome] = []  # non-tie, non-dead hands
        self.ref: Optional[List[Outcome]] = None
        self.marks: List[bool] = []
        self.active = False
        self.window_left = 0        # remaining hands in the current betting window
        self.bet_side: Optional[Outcome] = None
        self.step = 0               # Martingale step
        self.consumed_marks = 0     # guard against re-triggering on the same marks

    # ---- decision -------------------------------------------------------- #
    def next_bet(self) -> PlacedBet:
        if not self.active or self.window_left <= 0 or self.bet_side is None:
            return None
        # The next non-tie hand sits at index self.nt_count; skip the dead hand.
        if self.nt_count % 4 == 3:
            return None
        return (self.bet_side, self.base * (2 ** self.step))

    # ---- event ----------------------------------------------------------- #
    def observe(self, outcome: Outcome, won: Optional[bool]) -> None:
        # Update the Martingale / window based on a placed bet's result.
        if won is True:
            self.step = 0
            self.window_left = 0          # secured a small profit; close the window
        elif won is False:
            self.window_left -= 1
            if self.window_left <= 0:
                self.step = 0             # window exhausted; accept the loss
            else:
                self.step = min(self.step + 1, self.max_marts)
        # won is None: no bet placed or a tie pushed; leave progression as-is.

        if outcome is Outcome.TIE:
            return  # ignored entirely

        idx = self.nt_count
        self.nt_count += 1
        if idx % 4 == 3:
            return  # dead hand -- not part of the live stream

        self.live.append(outcome)
        if len(self.live) % 3 == 0:
            self._complete_set()

    def _complete_set(self) -> None:
        s = self.live[-3:]
        if self.ref is None:
            if len(set(s)) > 1:  # first non-uniform set becomes the reference
                self.ref = s
            return

        for j in range(3):
            self.marks.append(s[j] is self.ref[j])

        if len(self.marks) >= 3 and len(self.marks) > self.consumed_marks:
            if self.marks[-1] == self.marks[-2] == self.marks[-3]:
                self.active = True
                self.bet_side = _opposite(self.live[-1])
                self.window_left = 3
                self.step = 0
                self.consumed_marks = len(self.marks)


def default_systems(base: float = 1.0) -> List[BettingSystem]:
    """Representative set of systems for the bankroll backtester."""
    return [
        FlatBanker(base),
        MartingaleBanker(base),
        ParoliBanker(base),
        HongKongLady(base),
    ]
