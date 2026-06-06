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

### Web app (recommended for streaming / OBS)

Just open **`tracker.html`** in any browser — double-click the file, or in OBS
add a *Browser Source* pointing at it. No install, no Python needed.

It gives you:
- A casino-style **Big Road** and **Bead Plate** scoreboard
- Big **BANKER / PLAYER / TIE** buttons (plus UNDO / RESET)
- **Live odds** bars and the lowest-edge bet
- A **card-count mode**: tap each dealt card and it recomputes the *true* odds
  from the remaining shoe via in-browser Monte Carlo
- **Strategy signals** that light up for B-P-B-P, streaks, chop, and Hong Kong
  Lady
- A **session P/L** readout for flat Banker betting

### Visual desktop app (Tkinter)

```bash
python app.py
```

A simpler desktop window with the same buttons and a Pattern Watch panel. Uses
Tkinter, which ships with Python — no extra install. On Windows use
`python app.py` (not `python3`).

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
| `baccarat/systems.py` | Stateful betting systems with money management: Flat, Martingale, Paroli, Hong Kong Lady. |
| `baccarat/backtest.py` | Runs strategies and systems over many shoes; reports ROI, risk of ruin, max stake. |
| `tracker.html` | Self-contained web app for live use / OBS: scoreboards, live odds, card counting, signals. |
| `app.py` | Visual desktop tracker (Tkinter): click to log hands, see live odds and pattern alerts. |
| `baccarat/vision.py` | Optional screen-capture + template-matching card/result detector (OpenCV). |
| `detect.py` | CLI to calibrate and run auto-detection from your screen. |
| `main.py` | Command-line demo tying it all together. |

## Auto-detection from your screen (optional, advanced)

`detect.py` can watch a region of your screen and log results automatically via
template matching, so you don't have to click.

**Please read before using:**
- It does **not** improve your odds. It only saves clicks. Banker stays ~50.68%.
- **Many casinos forbid automated tools in real-money play** and may close your
  account / confiscate funds. Use it on demos, replays, or play-money tables.
  You are responsible for following your casino's rules.

**Setup:**
```bash
pip install opencv-python mss numpy        # extra libraries (one time)

# 1. Capture the result area to a PNG so you can crop templates from it
python detect.py --grab --left 800 --top 600 --width 240 --height 120

# 2. Crop the Banker/Player/Tie indicators from region_snapshot.png and save
#    them as templates/B.png, templates/P.png, templates/T.png

# 3. Save your configuration
python detect.py --save-config --left 800 --top 600 --width 240 --height 120

# 4. Run live detection (prints each detected result + live odds)
python detect.py --run
```

It must be calibrated to your specific screen and casino graphics — there is no
universal detector.

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

## Betting systems & money management

`baccarat/systems.py` implements full systems (which side **and** how much),
including the popular **Hong Kong Lady** (sets of three, skip the 4th "dead
hand", ignore ties, pattern-match marks, then bet the opposite with a
Martingale). Backtested over 5,000 shoes with a 200-unit bankroll per session:

| System | Win% | ROI | Risk of Ruin | Worst Session |
|--------|------|-----|--------------|---------------|
| Flat Banker | 50.6% | -1.1% | 0% | -31 |
| Martingale Banker | 50.6% | -1.7% | **~21%** | **-129** |
| Paroli Banker | 50.6% | -1.1% | 0% | -47 |
| Hong Kong Lady | 50.2% | -0.5% | 0% | -21 |

The takeaway: **money management changes the *shape* of results, not the edge.**
Martingale produces many small wins but a real chance of catastrophic loss when
a normal losing streak collides with your bankroll/table limit. Hong Kong Lady
just bets fewer hands; its expectation is still negative. (Numbers vary slightly
per run/seed.)

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
