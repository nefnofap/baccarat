"""Baccarat Live Tracker -- a visual desktop app for tracking a baccarat shoe.

Run:  python app.py

A window opens with big BANKER / PLAYER / TIE buttons. Click one each time a
hand resolves and the app updates:
  - a casino-style scoreboard (colored beads)
  - the running counts and win percentages
  - the true next-hand probabilities and the best bet (always Banker)
  - a "Pattern Watch" panel that flags your B-P-B-P chop, streaks, and zigzags

It also has a built-in AUTO-DETECT bar:
  - "Snip result area" opens a drag-to-select overlay to mark where the result
    shows on your screen
  - "Capture B/P/T" snaps one example of each outcome (teach by example)
  - "Start detecting" watches that area and logs results for you automatically
Auto-detect needs:  python -m pip install opencv-python mss numpy
(The manual buttons work without those libraries.)

Built with Tkinter, which ships inside Python -- no extra install needed.

HONESTY NOTE shown in the UI:
Baccarat hands are independent, so the probability of the next hand does NOT
change based on past results. The pattern panel is there because you asked to
track your B-P-B-P idea live; it shows what each system *would* bet, but the
underlying odds stay the same (~50.68% Banker among non-tie hands). Auto-detect
only saves you clicks; it does not provide an edge. Treat all signals as
entertainment, not a winning system.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import font as tkfont, messagebox
from typing import List, Optional

from baccarat.engine import Outcome
from baccarat.strategies import (
    user_alternating_then_banker,
    make_follow_streak,
    make_chop_follow,
)

# Optional auto-detection. The app works fully without these; the detection
# controls simply explain what to install if the libraries are missing.
try:
    from baccarat import vision
    _VISION_IMPORT_OK = True
except Exception:  # pragma: no cover - defensive
    vision = None  # type: ignore
    _VISION_IMPORT_OK = False

CONFIG_PATH = "detector_config.json"
TEMPLATE_DIR = "templates"


# ---- Colors / theme (casino style, reads well on stream) ------------------ #
BG = "#0b132b"          # deep navy background
PANEL = "#1c2541"       # panel background
PANEL2 = "#26314f"      # lighter panel / secondary button
TEXT = "#e0e1dd"        # light text
MUTED = "#8d99ae"       # muted text
BANKER_C = "#e63946"    # red
PLAYER_C = "#457b9d"    # blue
TIE_C = "#2a9d8f"       # green
ACCENT = "#ffd166"      # gold highlight

# True baccarat probabilities for a fresh 8-deck shoe (published figures).
P_BANKER = 0.4586
P_PLAYER = 0.4462
P_TIE = 0.0952
P_BANKER_NONTIE = 0.5068  # banker win rate excluding ties


class BaccaratApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.history: List[Outcome] = []

        # pattern strategies reused from the package
        self._streak = make_follow_streak(3)
        self._chop = make_chop_follow(3)

        # auto-detection state
        self._region = None              # vision.Region once selected
        self._detector_thread: Optional[threading.Thread] = None
        self._detecting = False

        root.title("Baccarat Live Tracker")
        root.configure(bg=BG)
        root.minsize(900, 700)

        self._fonts()
        self._build_header()
        self._build_body()
        self._build_detect_bar()
        self._build_buttons()
        self.refresh()

    # ----------------------------------------------------------------- setup
    def _fonts(self) -> None:
        self.f_title = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self.f_h2 = tkfont.Font(family="Segoe UI", size=14, weight="bold")
        self.f_big = tkfont.Font(family="Segoe UI", size=34, weight="bold")
        self.f_body = tkfont.Font(family="Segoe UI", size=12)
        self.f_small = tkfont.Font(family="Segoe UI", size=10)
        self.f_btn = tkfont.Font(family="Segoe UI", size=18, weight="bold")

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(
            header, text="BACCARAT LIVE TRACKER", font=self.f_title,
            fg=ACCENT, bg=BG,
        ).pack(side="left")
        tk.Label(
            header,
            text="Banker is always the best bet (1.06% edge). Patterns do not change the odds.",
            font=self.f_small, fg=MUTED, bg=BG,
        ).pack(side="right")

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=8)

        # Left: scoreboard
        left = tk.Frame(body, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(left, text="Scoreboard", font=self.f_h2, fg=TEXT, bg=PANEL).pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        self.canvas = tk.Canvas(
            left, bg=PANEL, highlightthickness=0, height=260
        )
        self.canvas.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.counts_lbl = tk.Label(
            left, text="", font=self.f_body, fg=MUTED, bg=PANEL, justify="left"
        )
        self.counts_lbl.pack(anchor="w", padx=14, pady=(0, 12))

        # Right: odds + pattern watch
        right = tk.Frame(body, bg=PANEL, width=320)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Next hand odds", font=self.f_h2, fg=TEXT, bg=PANEL).pack(
            anchor="w", padx=14, pady=(12, 6)
        )
        self.odds_lbl = tk.Label(
            right, text="", font=self.f_body, fg=TEXT, bg=PANEL, justify="left"
        )
        self.odds_lbl.pack(anchor="w", padx=14)

        tk.Label(
            right, text="Best bet", font=self.f_small, fg=MUTED, bg=PANEL
        ).pack(anchor="w", padx=14, pady=(12, 0))
        self.bestbet_lbl = tk.Label(
            right, text="BANKER", font=self.f_big, fg=BANKER_C, bg=PANEL
        )
        self.bestbet_lbl.pack(anchor="w", padx=14)

        tk.Label(
            right, text="Pattern Watch", font=self.f_h2, fg=TEXT, bg=PANEL
        ).pack(anchor="w", padx=14, pady=(16, 6))
        self.pattern_lbl = tk.Label(
            right, text="", font=self.f_body, fg=TEXT, bg=PANEL,
            justify="left", wraplength=290,
        )
        self.pattern_lbl.pack(anchor="w", padx=14, pady=(0, 12))

    def _build_detect_bar(self) -> None:
        """Auto-detection controls embedded in the UI (snip + start/stop)."""
        wrap = tk.Frame(self.root, bg=PANEL)
        wrap.pack(fill="x", padx=20, pady=(0, 6))

        row = tk.Frame(wrap, bg=PANEL)
        row.pack(fill="x", padx=12, pady=10)

        tk.Label(
            row, text="Auto-detect", font=self.f_h2, fg=TEXT, bg=PANEL
        ).pack(side="left", padx=(0, 12))

        self.snip_btn = tk.Button(
            row, text="SNIP RESULT AREA", font=self.f_small, bg=ACCENT, fg="#1a1a1a",
            activebackground=ACCENT, relief="flat", bd=0, padx=12, pady=8,
            command=self.on_snip, cursor="hand2",
        )
        self.snip_btn.pack(side="left", padx=4)

        self.capture_btn = tk.Button(
            row, text="CAPTURE B/P/T", font=self.f_small, bg=PANEL2, fg=TEXT,
            activebackground=PANEL2, relief="flat", bd=0, padx=12, pady=8,
            command=self.on_capture, cursor="hand2", state="disabled",
        )
        self.capture_btn.pack(side="left", padx=4)

        self.detect_btn = tk.Button(
            row, text="START DETECTING", font=self.f_small, bg=TIE_C, fg="white",
            activebackground=TIE_C, relief="flat", bd=0, padx=12, pady=8,
            command=self.on_toggle_detect, cursor="hand2", state="disabled",
        )
        self.detect_btn.pack(side="left", padx=4)

        self.detect_status = tk.Label(
            row, text="", font=self.f_small, fg=MUTED, bg=PANEL
        )
        self.detect_status.pack(side="left", padx=12)

        self._set_detect_status()

    def _set_detect_status(self, msg: Optional[str] = None) -> None:
        if msg is not None:
            self.detect_status.config(text=msg)
            return
        if not _VISION_IMPORT_OK or vision is None or not vision.deps_available():
            self.detect_status.config(
                text="Install once:  python -m pip install opencv-python mss numpy"
            )
            self.snip_btn.config(state="disabled")
        elif self._region is None and not os.path.exists(CONFIG_PATH):
            self.detect_status.config(text="Step 1: snip the result area.")
        elif not self._templates_ready():
            self.detect_status.config(text="Step 2: capture one B, P and T example.")
        else:
            self.detect_status.config(text="Ready. Press Start detecting.")

    def _templates_ready(self) -> bool:
        return all(
            os.path.exists(os.path.join(TEMPLATE_DIR, f"{x}.png"))
            for x in ("B", "P", "T")
        )

    # ---- detection actions ---------------------------------------------- #
    def on_snip(self) -> None:
        if not _VISION_IMPORT_OK or vision is None or not vision.deps_available():
            messagebox.showinfo(
                "Install required",
                "Auto-detection needs extra libraries.\n\n"
                "Run this once in a terminal:\n"
                "    python -m pip install opencv-python mss numpy\n\n"
                "Then reopen the app.",
            )
            return
        try:
            from baccarat.snipper import select_region
        except Exception as exc:
            messagebox.showerror("Snipping unavailable", str(exc))
            return

        # Hide our window so it doesn't cover the casino screen during selection.
        self.root.withdraw()
        self.root.update()
        try:
            region = select_region()
        finally:
            self.root.deiconify()

        if region is None:
            self._set_detect_status("Snip cancelled.")
            return

        self._region = region
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        config = vision.DetectorConfig(region=region, template_dir=TEMPLATE_DIR)
        config.to_json(CONFIG_PATH)
        self.capture_btn.config(state="normal")
        self._set_detect_status(
            f"Region saved ({region.width}x{region.height}). Now capture B/P/T."
        )
        self._maybe_enable_detect()

    def on_capture(self) -> None:
        """Capture one example each of Banker, Player, Tie from the live screen."""
        if self._region is None:
            if os.path.exists(CONFIG_PATH):
                self._region = vision.DetectorConfig.from_json(CONFIG_PATH).region
            else:
                messagebox.showinfo("Snip first", "Select the result area first.")
                return

        for label, name in (("B", "BANKER"), ("P", "PLAYER"), ("T", "TIE")):
            messagebox.showinfo(
                f"Capture {name}",
                f"Make sure a {name} result is showing on screen, then click OK.",
            )
            img = vision.grab(self._region)
            os.makedirs(TEMPLATE_DIR, exist_ok=True)
            vision.save_png(img, os.path.join(TEMPLATE_DIR, f"{label}.png"))

        self._set_detect_status("Templates captured. Ready to detect.")
        self._maybe_enable_detect()

    def _maybe_enable_detect(self) -> None:
        if self._templates_ready() and os.path.exists(CONFIG_PATH):
            self.detect_btn.config(state="normal")

    def on_toggle_detect(self) -> None:
        if self._detecting:
            self._detecting = False
            self.detect_btn.config(text="START DETECTING", bg=TIE_C)
            self._set_detect_status("Detection stopped.")
            return

        if not (self._templates_ready() and os.path.exists(CONFIG_PATH)):
            messagebox.showinfo("Not ready", "Snip the area and capture B/P/T first.")
            return

        # Honest reminder before auto-detecting against a live feed.
        messagebox.showwarning(
            "Before you start",
            "Auto-detection only saves clicks - it does NOT change the odds "
            "(Banker stays ~50.68%).\n\nMany casinos forbid automated tools in "
            "real-money play and may suspend accounts. Best used on demo or "
            "play-money tables. You are responsible for following the rules.",
        )

        self._detecting = True
        self.detect_btn.config(text="STOP DETECTING", bg=BANKER_C)
        self._set_detect_status("Watching the screen...")
        self._start_detector_thread()

    def _start_detector_thread(self) -> None:
        config = vision.DetectorConfig.from_json(CONFIG_PATH)
        try:
            detector = vision.ResultDetector(config)
        except Exception as exc:
            self._detecting = False
            self.detect_btn.config(text="START DETECTING", bg=TIE_C)
            messagebox.showerror("Detector error", str(exc))
            return

        label_map = {"B": Outcome.BANKER, "P": Outcome.PLAYER, "T": Outcome.TIE}

        def on_result(label: str) -> None:
            outcome = label_map.get(label)
            if outcome is not None:
                # Hop back to the UI thread to mutate state safely.
                self.root.after(0, lambda: self.add(outcome))

        def worker() -> None:
            detector.run(
                on_result,
                stable_frames=2,
                stop=lambda: not self._detecting,
            )

        self._detector_thread = threading.Thread(target=worker, daemon=True)
        self._detector_thread.start()

    def _build_buttons(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=20, pady=(4, 18))

        def mkbtn(text, color, cmd):
            return tk.Button(
                bar, text=text, font=self.f_btn, bg=color, fg="white",
                activebackground=color, activeforeground="white",
                relief="flat", bd=0, padx=10, pady=14, command=cmd,
                cursor="hand2",
            )

        mkbtn("BANKER", BANKER_C, lambda: self.add(Outcome.BANKER)).pack(
            side="left", expand=True, fill="x", padx=4
        )
        mkbtn("PLAYER", PLAYER_C, lambda: self.add(Outcome.PLAYER)).pack(
            side="left", expand=True, fill="x", padx=4
        )
        mkbtn("TIE", TIE_C, lambda: self.add(Outcome.TIE)).pack(
            side="left", expand=True, fill="x", padx=4
        )
        tk.Button(
            bar, text="UNDO", font=self.f_btn, bg=PANEL, fg=TEXT,
            activebackground=PANEL, activeforeground=TEXT, relief="flat",
            bd=0, padx=10, pady=14, command=self.undo, cursor="hand2",
        ).pack(side="left", expand=True, fill="x", padx=4)
        tk.Button(
            bar, text="RESET", font=self.f_btn, bg="#3a0ca3", fg="white",
            activebackground="#3a0ca3", activeforeground="white", relief="flat",
            bd=0, padx=10, pady=14, command=self.reset, cursor="hand2",
        ).pack(side="left", expand=True, fill="x", padx=4)

    # --------------------------------------------------------------- actions
    def add(self, outcome: Outcome) -> None:
        self.history.append(outcome)
        self.refresh()

    def undo(self) -> None:
        if self.history:
            self.history.pop()
            self.refresh()

    def reset(self) -> None:
        self.history.clear()
        self.refresh()

    # --------------------------------------------------------------- drawing
    def _draw_scoreboard(self) -> None:
        c = self.canvas
        c.delete("all")
        c.update_idletasks()
        w = c.winfo_width() or 520
        r = 16          # bead radius
        gap = 8
        cell = 2 * r + gap
        cols = max(1, (w - 14) // cell)

        color = {
            Outcome.BANKER: BANKER_C,
            Outcome.PLAYER: PLAYER_C,
            Outcome.TIE: TIE_C,
        }
        letter = {Outcome.BANKER: "B", Outcome.PLAYER: "P", Outcome.TIE: "T"}

        for i, o in enumerate(self.history):
            row, col = divmod(i, cols)
            x = 8 + col * cell + r
            y = 8 + row * cell + r
            c.create_oval(
                x - r, y - r, x + r, y + r, fill=color[o], outline=""
            )
            c.create_text(
                x, y, text=letter[o], fill="white", font=self.f_small
            )

    def _counts_text(self) -> str:
        b = self.history.count(Outcome.BANKER)
        p = self.history.count(Outcome.PLAYER)
        t = self.history.count(Outcome.TIE)
        n = len(self.history)
        if n == 0:
            return "No hands recorded yet. Click a button after each result."
        return (
            f"Hands: {n}    Banker: {b} ({b/n:.0%})    "
            f"Player: {p} ({p/n:.0%})    Tie: {t} ({t/n:.0%})"
        )

    def _odds_text(self) -> str:
        return (
            f"Banker  {P_BANKER:.1%}\n"
            f"Player  {P_PLAYER:.1%}\n"
            f"Tie     {P_TIE:.1%}\n\n"
            f"Excluding ties, Banker wins\n{P_BANKER_NONTIE:.2%} of hands -- always."
        )

    def _pattern_text(self) -> str:
        lines: List[str] = []

        bpbp = user_alternating_then_banker(self.history)
        if bpbp is not None:
            lines.append("* B-P-B-P chop detected -> your system says BANKER.")
        else:
            lines.append("- B-P-B-P chop: not present.")

        streak = self._streak(self.history)
        if streak is not None:
            lines.append(f"* Streak of 3+ -> follow says {streak.value.upper()}.")
        else:
            lines.append("- Streak (3+): not present.")

        chop = self._chop(self.history)
        if chop is not None:
            lines.append(f"* Zigzag run -> chop says {chop.value.upper()}.")
        else:
            lines.append("- Zigzag (3+): not present.")

        lines.append(
            "\nReminder: these signals do not improve your odds. The next "
            "hand is still ~50.68% Banker regardless."
        )
        return "\n".join(lines)

    def refresh(self) -> None:
        self._draw_scoreboard()
        self.counts_lbl.config(text=self._counts_text())
        self.odds_lbl.config(text=self._odds_text())
        self.pattern_lbl.config(text=self._pattern_text())


def main() -> None:
    root = tk.Tk()
    BaccaratApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
