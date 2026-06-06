"""Drag-to-select "snipping tool" for choosing a screen region.

This gives the calibration step a friendly UI: a translucent full-screen overlay
that you click-and-drag across, exactly like the Windows Snipping Tool. It
returns the selected rectangle as a Region.

It uses Tkinter, which ships with Python, so picking a region needs NO extra
install. (Capturing pixels for templates / live detection still uses mss +
OpenCV, but selecting the area does not.)

Returns None if the user presses Escape or closes the overlay.
"""

from __future__ import annotations

import tkinter as tk
from typing import Optional

from .vision import Region


class _SnipOverlay:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.start_x = 0
        self.start_y = 0
        self.rect = None
        self.region: Optional[Region] = None

        # Full-screen, semi-transparent, always-on-top overlay.
        root.attributes("-fullscreen", True)
        try:
            root.attributes("-alpha", 0.30)
        except tk.TclError:
            pass  # some platforms ignore alpha; still usable
        root.attributes("-topmost", True)
        root.configure(bg="black")
        root.config(cursor="crosshair")

        self.canvas = tk.Canvas(root, highlightthickness=0, bg="black")
        self.canvas.pack(fill="both", expand=True)

        # Helper hint text.
        self.canvas.create_text(
            root.winfo_screenwidth() // 2, 40,
            text="Drag to select the result area  -  Enter to confirm  -  Esc to cancel",
            fill="white", font=("Segoe UI", 16, "bold"),
        )

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        root.bind("<Escape>", lambda e: self._cancel())
        root.bind("<Return>", lambda e: self._confirm())

    def _on_press(self, event) -> None:
        self.start_x, self.start_y = event.x, event.y
        if self.rect is not None:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#ffd166", width=2, fill="#ffd166", stipple="gray25",
        )

    def _on_drag(self, event) -> None:
        if self.rect is not None:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event) -> None:
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        if x2 - x1 >= 5 and y2 - y1 >= 5:
            self.region = Region(left=x1, top=y1, width=x2 - x1, height=y2 - y1)

    def _confirm(self) -> None:
        # Confirm on Enter only if we have a selection; otherwise keep waiting.
        if self.region is not None:
            self.root.destroy()

    def _cancel(self) -> None:
        self.region = None
        self.root.destroy()


def select_region() -> Optional[Region]:
    """Open the snipping overlay and return the chosen Region (or None)."""
    root = tk.Tk()
    root.title("Select baccarat result area")
    overlay = _SnipOverlay(root)
    root.mainloop()
    return overlay.region
