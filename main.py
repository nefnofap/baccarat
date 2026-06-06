"""Baccarat probability & strategy demo.

Run:  python main.py

It does three things:
  1. Shows the outcome probabilities at the start of a fresh 8-deck shoe and
     the expected value (house edge) of each bet.
  2. Demonstrates "card counting": removes some cards and recomputes, so you
     can see how little the odds move.
  3. Backtests several strategies -- flat Banker, the user's B-P-B-P -> Banker
     idea, follow-the-streak (dragon), and chop -- over many shoes, and prints
     a comparison so you can judge them on ROI, not folklore.
"""

from __future__ import annotations

from baccarat.engine import Shoe
from baccarat.calculator import (
    probabilities_from_remaining,
    bet_expected_values,
)
from baccarat.strategies import default_strategies
from baccarat.backtest import (
    backtest,
    format_results,
    backtest_systems,
    format_system_results,
)
from baccarat.systems import default_systems


def section(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def show_fresh_shoe_odds(seed: int = 1) -> None:
    section("1) Fresh 8-deck shoe: outcome odds and house edge")
    shoe = Shoe()
    probs = probabilities_from_remaining(
        shoe.remaining_counts(), trials=300_000, seed=seed
    )
    print(probs)

    evs = bet_expected_values(probs)
    print("\nExpected value per 1 unit staked (negative = house edge):")
    for bet, ev in evs.items():
        print(f"  {bet:<7} EV = {ev:+.4f}  (house edge {-ev:.2%})")
    print(
        "\nBanker is always the least-bad bet. This never changes with patterns."
    )


def show_card_counting_effect(seed: int = 2) -> None:
    section("2) 'Card counting': how much do removed cards move the odds?")
    shoe = Shoe()

    base = probabilities_from_remaining(
        shoe.remaining_counts(), trials=300_000, seed=seed
    )
    print(f"Full shoe:           {base}")

    # Remove a chunk of low cards (often cited as helping Player slightly).
    counts = shoe.remaining_counts()
    for value in (1, 2, 3, 4):  # remove many Aces/2s/3s/4s
        counts[value] = max(0, counts[value] - 40)
    skewed = probabilities_from_remaining(counts, trials=300_000, seed=seed)
    print(f"After removing lows: {skewed}")

    db = skewed.banker - base.banker
    dp = skewed.player - base.player
    print(
        f"\nShift:  Banker {db:+.3%}   Player {dp:+.3%}"
        "\nEven an extreme, unrealistic removal barely nudges the odds --"
        "\nwhich is why baccarat card counting is not practically exploitable."
    )


def run_backtest(seed: int = 42) -> None:
    section("3) Strategy backtest (identical hands for every strategy)")
    strategies = default_strategies()
    print("Strategies under test:")
    for s in strategies:
        print(f"  - {s.name}: {s.description}")

    print("\nSimulating 5,000 shoes...\n")
    results = backtest(strategies, num_shoes=5_000, seed=seed)
    print(format_results(results))

    print(
        "\nRead the ROI column: every strategy lands near the same negative ROI"
        "\nas flat Banker betting (~-1% to -1.3%). Selecting hands by pattern"
        "\n(B-P-B-P, streaks, chop) does not produce a positive expectation,"
        "\nbecause each hand is independent. The only real lever is bet choice"
        "\n(Banker has the smallest edge) and bankroll/risk management."
    )


def run_systems_backtest(seed: int = 7) -> None:
    section("4) Money-management systems (Hong Kong Lady, Martingale, Paroli)")
    systems = default_systems(base=1.0)
    print("Each shoe is one session starting with a 200-unit bankroll.\n")
    results = backtest_systems(systems, num_shoes=5_000, bankroll=200.0, seed=seed)
    print(format_system_results(results))
    print(
        "\nNotice: every system's ROI is still negative (~-1%), because money"
        "\nmanagement cannot beat an independent game. Martingale shows the"
        "\ntrap clearly -- a high win rate and steady small gains, but a large"
        "\nmax bet, real risk of ruin, and brutal worst sessions when a losing"
        "\nstreak finally lands. Hong Kong Lady is just pattern selection plus a"
        "\ncapped Martingale: same negative expectation, fewer hands bet."
    )


def main() -> None:
    show_fresh_shoe_odds()
    show_card_counting_effect()
    run_backtest()
    run_systems_backtest()
    print("\nDone.")


if __name__ == "__main__":
    main()
