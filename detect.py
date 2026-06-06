"""Auto-detect baccarat results from your screen (calibration + live run).

This is the optional computer-vision front end. It must be calibrated to YOUR
screen once, then it can watch the result area and log outcomes automatically.

PLEASE READ
-----------
* Auto-detection does NOT improve your odds. It only saves you from clicking.
* Many casinos forbid automated tools during real-money play -- you risk having
  your account closed. Use on demos / replays / play-money tables.
* Requires extra libraries:  pip install opencv-python mss numpy

EASIEST USAGE -- the snipping tool (recommended)
------------------------------------------------
       python detect.py --snip
   A translucent overlay appears (like the Windows Snipping Tool). Drag a box
   around the area where the result shows, press Enter, and it walks you through
   capturing one example each of Banker, Player, and Tie. Then just run it.

MANUAL USAGE (if you prefer typing coordinates)
-----------------------------------------------
1) Capture the result area so you can crop templates from it:
       python detect.py --grab --left 800 --top 600 --width 240 --height 120
   This saves 'region_snapshot.png'. Open it, crop the Banker/Player/Tie
   indicators, and save them into the templates folder as B.png, P.png, T.png.

2) Save your configuration:
       python detect.py --save-config --left 800 --top 600 --width 240 --height 120

RUN LIVE DETECTION (after either setup above)
---------------------------------------------
       python detect.py --run
   Prints each detected result + live odds. Press Ctrl+C to stop.
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


def cmd_snip(args) -> None:
    """Guided point-and-click calibration: drag a box, then teach B/P/T."""
    vision = _need_vision()
    try:
        from baccarat.snipper import select_region
    except Exception as exc:  # pragma: no cover - tkinter missing is rare
        print(f"Could not open the snipping overlay: {exc}")
        print("Falling back: use --grab/--save-config with manual coordinates.")
        sys.exit(1)

    print("Opening the snipping overlay -- drag a box around the RESULT area.")
    print("(Tip: frame just the spot where B / P / T appears, then press Enter.)")
    region = select_region()
    if region is None:
        print("Cancelled. No region selected.")
        sys.exit(1)
    print(
        f"Selected region: left={region.left} top={region.top} "
        f"width={region.width} height={region.height}"
    )

    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    config = vision.DetectorConfig(
        region=region,
        template_dir=TEMPLATE_DIR,
        match_threshold=args.threshold,
        poll_seconds=args.poll,
        monitor_index=args.monitor,
    )
    config.to_json(CONFIG_PATH)
    print(f"Saved configuration to {CONFIG_PATH}.\n")

    # Teach-by-example: capture one frame per outcome from the live screen.
    steps = [("B", "BANKER"), ("P", "PLAYER"), ("T", "TIE")]
    print(
        "Now we'll capture one example of each result. Get the casino screen to\n"
        "show each outcome, then press Enter here to snap it. You can re-run\n"
        "--snip any time to redo these.\n"
    )
    for label, name in steps:
        input(f"  Show a {name} result on screen, then press Enter to capture... ")
        img = vision.grab(region, args.monitor)
        path = os.path.join(TEMPLATE_DIR, f"{label}.png")
        vision.save_png(img, path)
        print(f"    saved {path}")

    print(
        "\nCalibration complete. Start detecting with:\n"
        "    python detect.py --run"
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Baccarat screen auto-detector.")

    def add_region(sp):
        sp.add_argument("--left", type=int, default=0)
        sp.add_argument("--top", type=int, default=0)
        sp.add_argument("--width", type=int, default=240)
        sp.add_argument("--height", type=int, default=120)
        sp.add_argument("--monitor", type=int, default=1)

    # Flags style (so `python detect.py --grab ...` works as documented).
    p.add_argument("--snip", action="store_true",
                   help="drag-to-select region + guided template capture")
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
    if args.snip:
        cmd_snip(args)
    elif args.grab:
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
