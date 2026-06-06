"""Core baccarat game engine.

Implements the standard "Punto Banco" rules used in virtually every casino:
- 8-deck shoe (configurable).
- Card values: Ace=1, 2-9 face value, 10/J/Q/K = 0.
- A hand total is the sum of its cards modulo 10.
- Fixed, choice-free third-card ("tableau") rules for Player and Banker.

There are no decisions in baccarat: given the cards, the result is fully
determined. That is exactly why outcomes are statistically independent from
one hand to the next, and why no betting *pattern* can predict the future.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Outcome(str, Enum):
    """Result of a single coup (hand)."""

    BANKER = "Banker"
    PLAYER = "Player"
    TIE = "Tie"


# A "card" here is represented purely by its rank index 0..12
# (0 = Ace, 1 = '2', ... 8 = '9', 9..12 = 10/J/Q/K).
# Suits are irrelevant in baccarat, so we never track them.
RANKS_PER_DECK = 4  # four suits => four of each rank per deck
NUM_RANKS = 13


def card_value(rank: int) -> int:
    """Return the baccarat point value (0-9) for a rank index 0..12."""
    if rank == 0:
        return 1  # Ace
    if rank <= 8:
        return rank + 1  # '2'..'9'
    return 0  # 10, J, Q, K


def hand_total(cards: List[int]) -> int:
    """Total of a hand modulo 10."""
    return sum(card_value(c) for c in cards) % 10


@dataclass
class Shoe:
    """A shoe of one or more decks that can be dealt from and reshuffled."""

    num_decks: int = 8
    rng: random.Random = field(default_factory=random.Random)
    _cards: List[int] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.shuffle()

    def shuffle(self) -> None:
        """Refill and shuffle the shoe to a full set of cards."""
        self._cards = []
        for rank in range(NUM_RANKS):
            self._cards.extend([rank] * (RANKS_PER_DECK * self.num_decks))
        self.rng.shuffle(self._cards)

    def __len__(self) -> int:
        return len(self._cards)

    @property
    def cards_remaining(self) -> int:
        return len(self._cards)

    def deal(self) -> int:
        """Deal a single card (rank index) from the front of the shoe."""
        return self._cards.pop()

    def remaining_counts(self) -> List[int]:
        """Return counts of each of the 10 baccarat *values* (0..9) remaining.

        Index 0 -> value 0 (tens/faces), index k -> value k. This is the only
        information that matters for computing probabilities.
        """
        counts = [0] * 10
        for rank in self._cards:
            counts[card_value(rank)] += 1
        return counts


def _player_draws(player_total: int) -> bool:
    """Player draws a third card on totals 0-5, stands on 6-7."""
    return player_total <= 5


def _banker_draws(banker_total: int, player_third_value: Optional[int]) -> bool:
    """Banker third-card tableau.

    If the Player stood (drew no third card), Banker draws on 0-5, stands 6-7.
    Otherwise Banker's action depends on its total AND the *value* of the
    Player's third card.
    """
    if player_third_value is None:
        return banker_total <= 5

    if banker_total <= 2:
        return True
    if banker_total == 3:
        return player_third_value != 8
    if banker_total == 4:
        return 2 <= player_third_value <= 7
    if banker_total == 5:
        return 4 <= player_third_value <= 7
    if banker_total == 6:
        return player_third_value in (6, 7)
    return False  # 7 stands


@dataclass
class HandResult:
    outcome: Outcome
    player_cards: List[int]
    banker_cards: List[int]
    player_total: int
    banker_total: int


def play_hand(shoe: Shoe) -> HandResult:
    """Deal and fully resolve one coup from the given shoe, applying all rules."""
    player = [shoe.deal(), shoe.deal()]
    banker = [shoe.deal(), shoe.deal()]

    p_total = hand_total(player)
    b_total = hand_total(banker)

    # Naturals: if either side has 8 or 9 on the first two cards, play stops.
    natural = p_total >= 8 or b_total >= 8

    player_third_value: Optional[int] = None
    if not natural:
        if _player_draws(p_total):
            card = shoe.deal()
            player.append(card)
            player_third_value = card_value(card)
            p_total = hand_total(player)

        if _banker_draws(b_total, player_third_value):
            banker.append(shoe.deal())
            b_total = hand_total(banker)

    if p_total > b_total:
        outcome = Outcome.PLAYER
    elif b_total > p_total:
        outcome = Outcome.BANKER
    else:
        outcome = Outcome.TIE

    return HandResult(
        outcome=outcome,
        player_cards=player,
        banker_cards=banker,
        player_total=p_total,
        banker_total=b_total,
    )
