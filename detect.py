"""Auto-detect baccarat results from your screen (calibration + live run).

This is the optional computer-vision front end. It must be calibrated to YOUR
screen once, then it can watch the result area and log outcomes automatically.

PLEASE READ
-----------
* Auto-detection does NOT improve your odds. It only saves you from clicking.
* Many casinos forbid automated tools during real-money play -- you risk having
  your account closed. Use on demos / replays / play-money tables.
* Requires extra libraries:  pip install opencv-python mss numpy

USAGE
-----
1) Capture the result area so you can crop templates from it:
       python detect.py --grab --left 800 --top 600 --width 240 --height 120
   This saves 'region_snapshot.png'. Open it, crop the Banker/Player/Tie
   indicators, and save them into the templates folder as B.png, P.png, T.png.

2) Save your configuration:
       python detect.py --save-config --left 800 --top 600 --width 240 --height 120

3) Run live detection (prints each detected result + live odds):
       python detect.py --run

Tip: find pixel coordinates with any screenshot tool, or use --grab on a guess
and adjust until 'region_snapshot.png' tightly frames the result indicator.
"""

from __future__ import annotations

import argparse
import os
import sys

from baccarat.engine import Shoe
from baccarat.calculator import probabilities_from_remaining, bet_expected_values

CONFIG_PATH = "detector_config.json"
TEMPLATE_DIR = "templates"
SNAPSHOT_PATH = "region_snapshot.png"

WARNING = (
    "\n"
    "============================================================\n"
    " AUTO-DETECTION NOTICE\n"
    "------------------------------------------------------------\n"
    " * This does NOT improve your odds. Banker stays ~50.68%.\n"
    " * Many casinos BAN automated tools in real-money play and\n"
    "   may confiscate balances. Use on demos / play-money only.\n"
    " * You are responsible for following your casino's rules.\n"
    "============================================================\n"
)


def _need_vision():
    from baccarat import vision  # imported here so non-vision use never fails
    if not vision.deps_available():
        print(vision.INSTALL_HINT)
        sys.exit(1)
    return vision


def cmd_grab(args) -> None:
    vision = _need_vision()
    region = vision.Region(args.left, args.top, args.width, args.height)
    img = vision.grab(region, args.monitor)
    vision.save_png(img, SNAPSHOT_PATH)
    print(f"Saved {SNAPSHOT_PATH} ({args.width}x{args.height}).")
    print(
        "Open it, crop each result indicator, and save them as "
        f"'{TEMPLATE_DIR}/B.png', '{TEMPLATE_DIR}/P.png', '{TEMPLATE_DIR}/T.png'."
    )


def cmd_save_config(args) -> None:
    vision = _need_vision()
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    region = vision.Region(args.left, args.top, args.width, args.height)
    config = vision.DetectorConfig(
        region=region,
        template_dir=TEMPLATE_DIR,
        match_threshold=args.threshold,
        poll_seconds=args.poll,
        monitor_index=args.monitor,
    )
    config.to_json(CONFIG_PATH)
    print(f"Saved configuration to {CONFIG_PATH}.")
    print(f"Put your template images in '{TEMPLATE_DIR}/' (B.png, P.png, T.png).")


def _print_odds(shoe: Shoe) -> None:
    probs = probabilities_from_remaining(shoe.remaining_counts(), trials=60_000)
    evs = bet_expected_values(probs)
    best = max(evs, key=evs.get)
    print(f"   odds -> {probs}")
    print(f"   best bet (least edge): {best}")


def cmd_run(args) -> None:
    vision = _need_vision()
    if not os.path.exists(CONFIG_PATH):
        print(f"No {CONFIG_PATH} found. Run --save-config first.")
        sys.exit(1)

    print(WARNING)
    config = vision.DetectorConfig.from_json(CONFIG_PATH)
    detector = vision.ResultDetector(config)

    history = []
    shoe = Shoe()  # informational odds only; not the casino's real shoe

    label_map = {"B": "BANKER", "P": "PLAYER", "T": "TIE"}

    def on_result(label: str) -> None:
        name = label_map.get(label, label)
        history.append(label)
        print(f"\nDetected: {name}   (hand #{len(history)})")
        print(f"   sequence: {' '.join(history[-20:])}")
        _print_odds(shoe)

    print("Watching the screen. Press Ctrl+C to stop.\n")
    try:
        detector.run(on_result, stable_frames=args.stable)
    except KeyboardInterrupt:
        print("\nStopped. Final sequence:")
        print(" ".join(history))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Baccarat screen auto-detector.")
    sub = p.add_subparsers(dest="mode", required=False)

    def add_region(sp):
        sp.add_argument("--left", type=int, default=0)
        sp.add_argument("--top", type=int, default=0)
        sp.add_argument("--width", type=int, default=240)
        sp.add_argument("--height", type=int, default=120)
        sp.add_argument("--monitor", type=int, default=1)

    # Flags style (so `python detect.py --grab ...` works as documented).
    p.add_argument("--grab", action="store_true", help="capture region to PNG")
    p.add_argument("--save-config", action="store_true", help="write config JSON")
    p.add_argument("--run", action="store_true", help="run live detection")
    add_region(p)
    p.add_argument("--threshold", type=float, default=0.80)
    p.add_argument("--poll", type=float, default=1.0)
    p.add_argument("--stable", type=int, default=2)
    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.grab:
        cmd_grab(args)
    elif args.save_config:
        cmd_save_config(args)
    elif args.run:
        cmd_run(args)
    else:
        print(__doc__)
        print(WARNING)


if __name__ == "__main__":
    main()
