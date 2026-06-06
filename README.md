# Baccarat Probability & Strategy Toolkit

A small Python toolkit that answers two questions honestly:

1. **Given the cards remaining in the shoe, what is the probability of Banker /
   Player / Tie?** (the "card counting" question)
2. **Do pattern-betting strategies actually work?** (streaks, chop, and the
   "after B-P-B-P, bet Banker" idea)

It implements correct casino rules, a Monte Carlo probability calculator, a set
of pluggable strategies, and a backtester that runs them over thousands of
simulated shoes so you can compare them on **ROI**, not folklore.

## Quick start

### Visual app (recommended for live use / streaming)

```bash
python app.py
```

Opens a desktop window with big BANKER / PLAYER / TIE buttons, a casino-style
colored scoreboard, live odds, and a "Pattern Watch" panel that flags the
B-P-B-P chop, streaks, and zigzags as you log each hand. Uses Tkinter, which
ships with Python -- no extra install needed.

On Windows use `python app.py` (not `python3`).

### Command-line analysis

```bash
python main.py
```

This prints fresh-shoe odds, a card-counting demonstration, and a strategy
comparison table.

## Project layout

| File | Purpose |
|------|---------|
| `baccarat/engine.py` | Game rules: 8-deck shoe, card values, full third-card tableau, hand resolution. |
| `baccarat/calculator.py` | `probabilities_from_remaining()` and `bet_expected_values()` — odds and EV from whatever cards are left. |
| `baccarat/strategies.py` | Flat Banker, the B-P-B-P → Banker system, follow-the-streak (dragon), chop/zigzag. |
| `baccarat/backtest.py` | Runs strategies over many shoes; reports wins, coverage, net units, ROI. |
| `app.py` | Visual desktop tracker (Tkinter): click to log hands, see live odds and pattern alerts. |
| `main.py` | Command-line demo tying it all together. |

## What the numbers show

**Fresh 8-deck shoe** (matches published figures):

- Banker ≈ 45.9%, Player ≈ 44.6%, Tie ≈ 9.5%
- House edge: Banker **1.06%**, Player **1.24%**, Tie **~14%**

**Card counting:** even removing an extreme, unrealistic batch of low cards
moves the odds by a fraction of a percent — far too little to overcome the
house edge. This matches Thorp's *Fundamental Theorem of Card Counting*, which
proves no favorable counting strategy exists for the main baccarat bets.

**Pattern strategies (incl. B-P-B-P → Banker):** in backtests, every pattern
strategy lands at essentially the same negative ROI as flat Banker betting.
After a B-P-B-P chop, Banker still wins ~50.68% of the next non-tie hands —
exactly its baseline rate. The pattern carries no predictive information,
because baccarat hands are statistically independent.

## The honest takeaways

- **Banker is always the best bet** (lowest house edge). Avoid Tie.
- **No betting pattern predicts future outcomes.** Past results don't change
  the next hand's odds.
- The only real levers are **bet selection** (stick to Banker) and
  **bankroll / risk management** (set limits) — not outcome prediction.

This is a math and simulation exercise. It is not a system for beating the
casino, because mathematically there isn't one.

## Define and test your own strategy

A strategy is just a function `List[Outcome] -> Optional[Outcome]` (return the
side to bet, or `None` to skip). Add yours to `strategies.py`, drop it into
`default_strategies()`, and re-run `main.py` to see its ROI against the
baselines.
