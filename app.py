"""Baccarat Live Tracker -- a visual desktop app for tracking a baccarat shoe.

Run:  python app.py

A window opens with big BANKER / PLAYER / TIE buttons. Click one each time a
hand resolves and the app updates:
  - a casino-style scoreboard (colored beads)
  - the running counts and win percentages
  - the true next-hand probabilities and the best bet (always Banker)
  - a "Pattern Watch" panel that flags your B-P-B-P chop, streaks, and zigzags

Built with Tkinter, which ships inside Python -- no extra install needed.

HONESTY NOTE shown in the UI:
Baccarat hands are independent, so the probability of the next hand does NOT
change based on past results. The pattern panel is there because you asked to
track your B-P-B-P idea live; it shows what each system *would* bet, but the
underlying odds stay the same (~50.68% Banker among non-tie hands). Treat the
pattern signals as entertainment, not an edge.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import List

from baccarat.engine import Outcome
from baccarat.strategies import (
    user_alternating_then_banker,
    make_follow_streak,
    make_chop_follow,
)


# ---- Colors / theme (casino style, reads well on stream) ------------------ #
BG = "#0b132b"          # deep navy background
PANEL = "#1c2541"       # panel background
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

        root.title("Baccarat Live Tracker")
        root.configure(bg=BG)
        root.minsize(900, 620)

        self._fonts()
        self._build_header()
        self._build_body()
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
