"""Screen capture + card/result auto-detection for live-dealer baccarat.

WHAT THIS DOES
--------------
Watches a region of YOUR screen (where your casino shows the result or the
cards) and reports the outcome automatically, so you don't have to click. It
uses simple, robust template matching (OpenCV): you save a few reference
snippets once (calibration), and the detector matches new frames against them.

READ THIS FIRST -- IMPORTANT CAVEATS
------------------------------------
1. NO EDGE. Auto-detection only saves you clicks. It does NOT change the odds.
   The next hand is still ~50.68% Banker no matter what. If a tool ever implies
   it can predict the next result, it is wrong.

2. CASINO TERMS OF SERVICE. Most online casinos forbid automated software
   assistance during real-money play. Using this against a live casino feed can
   get your account suspended and your balance confiscated. You are responsible
   for checking your casino's rules. Prefer using this on replays, demos, or
   "play money" tables.

3. CALIBRATION REQUIRED. There is no universal detector. You must tell it which
   screen region to watch and provide reference images for B / P / T (or for the
   individual card ranks) from YOUR casino's specific graphics.

This module degrades gracefully: if OpenCV / mss / numpy are not installed, it
raises a clear, friendly error explaining how to install them.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

# Optional heavy deps -- imported lazily so the rest of the package works
# without them. We record whether they are available and why not.
_IMPORT_ERROR: Optional[str] = None
try:  # pragma: no cover - environment dependent
    import numpy as np  # type: ignore
    import cv2  # type: ignore
    import mss  # type: ignore

    _DEPS_OK = True
except Exception as exc:  # pragma: no cover - environment dependent
    _DEPS_OK = False
    _IMPORT_ERROR = str(exc)


INSTALL_HINT = (
    "Auto-detection needs extra libraries. Install them with:\n"
    "    pip install opencv-python mss numpy\n"
    "(On Windows use:  python -m pip install opencv-python mss numpy)"
)


def deps_available() -> bool:
    """True if OpenCV / mss / numpy imported successfully."""
    return _DEPS_OK


def require_deps() -> None:
    """Raise a friendly error if the optional vision deps are missing."""
    if not _DEPS_OK:
        raise RuntimeError(
            f"{INSTALL_HINT}\n\nUnderlying import error: {_IMPORT_ERROR}"
        )


# --------------------------------------------------------------------------- #
# Region / config
# --------------------------------------------------------------------------- #

@dataclass
class Region:
    """A rectangle of the screen to watch, in pixels."""

    left: int
    top: int
    width: int
    height: int

    def as_mss(self) -> Dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class DetectorConfig:
    """Everything needed to run detection, saved/loaded as JSON."""

    region: Region
    template_dir: str
    match_threshold: float = 0.80  # min normalized-correlation score to accept
    poll_seconds: float = 1.0      # how often to grab a frame
    monitor_index: int = 1         # mss monitor (1 = primary on most setups)

    def to_json(self, path: str) -> None:
        data = {
            "region": self.region.__dict__,
            "template_dir": self.template_dir,
            "match_threshold": self.match_threshold,
            "poll_seconds": self.poll_seconds,
            "monitor_index": self.monitor_index,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    @staticmethod
    def from_json(path: str) -> "DetectorConfig":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return DetectorConfig(
            region=Region(**data["region"]),
            template_dir=data["template_dir"],
            match_threshold=data.get("match_threshold", 0.80),
            poll_seconds=data.get("poll_seconds", 1.0),
            monitor_index=data.get("monitor_index", 1),
        )


# --------------------------------------------------------------------------- #
# Screen capture
# --------------------------------------------------------------------------- #

def grab(region: Region, monitor_index: int = 1):
    """Capture the given screen region and return it as a BGR numpy image."""
    require_deps()
    with mss.mss() as sct:
        # Build an absolute capture box relative to the chosen monitor.
        mon = sct.monitors[monitor_index]
        box = {
            "left": mon["left"] + region.left,
            "top": mon["top"] + region.top,
            "width": region.width,
            "height": region.height,
        }
        shot = sct.grab(box)
        img = np.array(shot)  # BGRA
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def save_png(image, path: str) -> None:
    """Save a captured image to disk (used by the calibration helper)."""
    require_deps()
    cv2.imwrite(path, image)


# --------------------------------------------------------------------------- #
# Template matching
# --------------------------------------------------------------------------- #

def _load_templates(template_dir: str) -> Dict[str, "np.ndarray"]:
    """Load every PNG in template_dir as {label: image}.

    The label is the filename without extension. For result detection use
    labels like 'B', 'P', 'T'. For card detection use e.g. '0','1'..'9'
    (baccarat point values) or rank names you choose.
    """
    require_deps()
    templates: Dict[str, np.ndarray] = {}
    if not os.path.isdir(template_dir):
        return templates
    for fn in sorted(os.listdir(template_dir)):
        if fn.lower().endswith((".png", ".jpg", ".jpeg")):
            label = os.path.splitext(fn)[0]
            img = cv2.imread(os.path.join(template_dir, fn), cv2.IMREAD_COLOR)
            if img is not None:
                templates[label] = img
    return templates


def best_match(frame, templates: Dict[str, "np.ndarray"]) -> Tuple[Optional[str], float]:
    """Return (label, score) of the template that best matches the frame.

    Uses normalized cross-correlation (TM_CCOEFF_NORMED). Templates larger than
    the frame are skipped. Score is in [-1, 1]; higher is a better match.
    """
    require_deps()
    best_label: Optional[str] = None
    best_score = -1.0
    for label, tmpl in templates.items():
        if tmpl.shape[0] > frame.shape[0] or tmpl.shape[1] > frame.shape[1]:
            # Resize template down to fit if needed.
            scale = min(
                frame.shape[0] / tmpl.shape[0],
                frame.shape[1] / tmpl.shape[1],
            )
            new_size = (max(1, int(tmpl.shape[1] * scale)),
                        max(1, int(tmpl.shape[0] * scale)))
            tmpl = cv2.resize(tmpl, new_size)
        res = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(res)
        if score > best_score:
            best_score = score
            best_label = label
    return best_label, best_score


# --------------------------------------------------------------------------- #
# Live detector loop
# --------------------------------------------------------------------------- #

class ResultDetector:
    """Polls the screen and fires a callback when a NEW result is detected.

    De-duplicates: the same result staying on screen across several frames is
    reported only once. A different result (or the region clearing and a new
    result appearing) is reported as a new hand.
    """

    def __init__(self, config: DetectorConfig) -> None:
        require_deps()
        self.config = config
        self.templates = _load_templates(config.template_dir)
        if not self.templates:
            raise RuntimeError(
                f"No template images found in '{config.template_dir}'. "
                "Run the calibration helper first (see detect.py --calibrate)."
            )
        self._last_label: Optional[str] = None
        self._stable_since: float = 0.0

    def read_once(self) -> Tuple[Optional[str], float]:
        """Grab one frame and return (label, score) for the best match."""
        frame = grab(self.config.region, self.config.monitor_index)
        return best_match(frame, self.templates)

    def run(
        self,
        on_result: Callable[[str], None],
        stable_frames: int = 2,
        stop: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Loop forever, calling on_result(label) once per new stable result.

        Args:
            on_result: called with the detected label ('B'/'P'/'T' or your set).
            stable_frames: require this many consecutive matching frames before
                accepting (reduces flicker / false positives during animations).
            stop: optional predicate; when it returns True the loop ends.
        """
        consec = 0
        candidate: Optional[str] = None
        while True:
            if stop is not None and stop():
                return
            label, score = self.read_once()
            accepted = label if score >= self.config.match_threshold else None

            if accepted is not None and accepted == candidate:
                consec += 1
            else:
                candidate = accepted
                consec = 1 if accepted is not None else 0

            if (
                accepted is not None
                and consec >= stable_frames
                and accepted != self._last_label
            ):
                self._last_label = accepted
                on_result(accepted)

            # When the region clears (no confident match), allow the same label
            # to be reported again on its next appearance.
            if accepted is None:
                self._last_label = None

            time.sleep(self.config.poll_seconds)
