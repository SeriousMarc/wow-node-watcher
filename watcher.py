import time
import winsound
from pathlib import Path

import cv2
import dxcam
import numpy as np

# --------------------
# CONFIG
# --------------------
FPS = 24
FRAME_INTERVAL = 1.0 / FPS

# Which monitor to capture (0 = primary, 1 = second, ...).
# Set to None to list monitors at startup and prompt for an index interactively.
MONITOR_INDEX = 0

# Physical monitor width (pixels) at which symbol_template.png was captured.
# Used to auto-scale the template and ROI when running on a different resolution.
# Common values: 1920 (1080p), 2560 (1440p/2K), 3840 (4K)
TEMPLATE_BASE_WIDTH = 2560

# Region of interest — set in physical pixels at TEMPLATE_BASE_WIDTH resolution.
# Automatically scaled to the current monitor's physical resolution at startup.
# (left, top, right, bottom) relative to the selected monitor.
ROI = (
    2228,
    109,
    2494,
    363,
)

# Path to the template image. Resolves relative to this script's directory.
TEMPLATE_PATH = Path(__file__).parent / "symbol_template.png"

MATCH_THRESHOLD = 0.9  # 0..1 — lower if missing detections, raise to reduce false positives

# A detection is confirmed after the match is stable for this many frames.
# A cleared detection is confirmed after it's absent for MISS_FRAMES_TO_CLEAR frames.
HIT_FRAMES_TO_CONFIRM = 1
MISS_FRAMES_TO_CLEAR = 12  # ~0.5s at 24 FPS

# Two matches closer than NMS_DIST_FRAC * template_size are treated as one symbol.
NMS_DIST_FRAC = 0.5

BEEP_FREQ = 1500  # Hz
BEEP_MS = 120     # ms

# --------------------
# LOAD TEMPLATE
# --------------------
template_bgr = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_COLOR)
if template_bgr is None:
    raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}\nSee README for capture instructions.")

template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)

# --------------------
# CAPTURE SETUP
# --------------------
if MONITOR_INDEX is None:
    print("Detected monitors:")
    print(dxcam.output_info())
    while True:
        raw = input("Enter monitor index to capture (e.g. 0): ").strip()
        try:
            MONITOR_INDEX = int(raw)
            break
        except ValueError:
            print("  Not a number, try again.")

camera = dxcam.create(output_idx=MONITOR_INDEX)
if camera is None:
    raise RuntimeError(
        f"dxcam.create returned None for output_idx={MONITOR_INDEX}. "
        f"Run with MONITOR_INDEX=None to list valid indices."
    )

# Scale template and ROI to match the current monitor's physical resolution.
# dxcam always captures physical pixels via DXGI, so coordinates must be in physical pixels.
_scale = camera.width / TEMPLATE_BASE_WIDTH
if abs(_scale - 1.0) > 0.01:
    print(f"Scaling by {_scale:.3f}x (monitor {camera.width}px wide, base {TEMPLATE_BASE_WIDTH}px)")
    template_gray = cv2.resize(
        template_gray,
        (int(template_gray.shape[1] * _scale), int(template_gray.shape[0] * _scale)),
        interpolation=cv2.INTER_LINEAR,
    )
    ROI = tuple(int(v * _scale) for v in ROI)
    print(f"Scaled ROI: {ROI}")

t_h, t_w = template_gray.shape[:2]

mon_h, mon_w = camera.height, camera.width
l, t, r, b = ROI
if r > mon_w or b > mon_h or l < 0 or t < 0:
    print(f"WARNING: ROI {ROI} is outside monitor bounds ({mon_w}x{mon_h}). Capture may be empty.")

_NMS_MIN_DIST = max(1, int(min(t_w, t_h) * NMS_DIST_FRAC))


def detect_symbols(frame_bgr: np.ndarray) -> tuple[int, float]:
    """Return (count, best_score) of distinct template matches in the frame."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    if gray.shape[0] < t_h or gray.shape[1] < t_w:
        return 0, 0.0

    res = cv2.matchTemplate(gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)

    ys, xs = np.where(res >= MATCH_THRESHOLD)
    if xs.size == 0:
        return 0, float(max_val)

    # Greedy non-max suppression: highest score first, suppress nearby candidates.
    scores = res[ys, xs]
    order = np.argsort(scores)[::-1]
    kept: list[tuple[int, int]] = []
    for i in order:
        x, y = int(xs[i]), int(ys[i])
        if all(abs(x - kx) >= _NMS_MIN_DIST or abs(y - ky) >= _NMS_MIN_DIST for kx, ky in kept):
            kept.append((x, y))

    return len(kept), float(max_val)


def beep() -> None:
    winsound.Beep(BEEP_FREQ, BEEP_MS)


def main() -> None:
    frame_count = 0
    stable_count = 0       # last confirmed symbol count
    pending_count = 0      # current observed count (not yet confirmed)
    frames_at_pending = 0  # consecutive frames at pending_count

    print("Starting capture... Press Ctrl+C to stop.")
    camera.start(region=ROI, target_fps=FPS)

    try:
        while True:
            start = time.perf_counter()
            frame = camera.get_latest_frame()

            if frame is not None:
                frame_count += 1
                count, score = detect_symbols(frame)

                if count == pending_count:
                    frames_at_pending += 1
                else:
                    pending_count = count
                    frames_at_pending = 1

                if pending_count != stable_count:
                    needed = HIT_FRAMES_TO_CONFIRM if pending_count > stable_count else MISS_FRAMES_TO_CLEAR
                    if frames_at_pending >= needed:
                        if pending_count > stable_count:
                            new_symbols = pending_count - stable_count
                            for _ in range(new_symbols):
                                beep()
                            print(f"DETECTED: {stable_count} -> {pending_count} (+{new_symbols}, score={score:.3f})")
                        else:
                            print(f"cleared: {stable_count} -> {pending_count}")
                        stable_count = pending_count

                if frame_count % FPS == 0:
                    print(f"frames: {frame_count} | now: {count} | stable: {stable_count} | score: {score:.3f}")

            elapsed = time.perf_counter() - start
            sleep_for = FRAME_INTERVAL - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        camera.stop()


if __name__ == "__main__":
    main()
