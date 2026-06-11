# wow-node-watcher

A lightweight Windows utility that watches a screen region for a WoW gathering node indicator and plays an audio alert the moment it appears.

Uses [dxcam](https://github.com/ra1nty/DXcam) for low-latency DXGI screen capture and OpenCV normalized template matching for detection. Automatically scales to any monitor resolution — configure once at your base resolution, works everywhere.

## How it works

1. Captures a configurable screen region at up to 24 FPS via DXGI Desktop Duplication (zero-copy, minimal CPU overhead)
2. Runs normalized cross-correlation (`TM_CCOEFF_NORMED`) between each frame and your template image
3. Applies non-maximum suppression to count distinct matches without double-counting
4. Plays a system beep the moment a stable match is detected

## Requirements

- Windows 10 / 11
- Python 3.14+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — fast Python package manager
- A DirectX-capable GPU (any modern discrete or integrated GPU)

## Setup

```bash
git clone https://github.com/yourusername/wow-node-watcher.git
cd wow-node-watcher
uv sync
```

## Capturing your template

The template is a tight crop of the node indicator icon as it appears on your display.

1. Wait until the node indicator is visible on screen
2. Use Snipping Tool (`Win+Shift+S`) to crop tightly around the icon — no padding
3. Save as `assets/symbol_template.png` in the project root
4. Set `TEMPLATE_BASE_WIDTH` in `watcher.py` to your monitor's physical pixel width at capture time

> `assets/symbol_template.png` is excluded from version control — each user captures their own.

## Configuration

Edit the `CONFIG` block at the top of `watcher.py`:

| Variable | Default | Description |
|---|---|---|
| `MONITOR_INDEX` | `0` | Monitor to capture. `0` = primary. Set to `None` to list monitors interactively at startup. |
| `TEMPLATE_BASE_WIDTH` | `2560` | Physical pixel width of the monitor when the template was captured. Common: `1920` (1080p), `2560` (1440p), `3840` (4K). |
| `ROI` | — | Region to watch `(left, top, right, bottom)` in physical pixels at `TEMPLATE_BASE_WIDTH` resolution. Auto-scales to the current monitor on startup. |
| `MATCH_THRESHOLD` | `0.8` | Match confidence `0.0–1.0`. Lower if detections are missed; raise to reduce false positives. |
| `HIT_FRAMES_TO_CONFIRM` | `1` | Consecutive frames a match must be present before alerting. |
| `MISS_FRAMES_TO_CLEAR` | `12` | Consecutive frames a match must be absent before re-arming (~0.5 s at 24 FPS). |
| `NMS_DIST_FRAC` | `0.5` | Fraction of template size used as the suppression radius for duplicate matches. |
| `BEEP_FREQ` | `1500` | Alert tone frequency in Hz. |
| `BEEP_MS` | `120` | Alert tone duration in milliseconds. |
| `FPS` | `24` | Capture rate. Higher values reduce reaction latency at the cost of CPU usage. |

## Usage

```bash
uv run watcher.py
```

Press `Ctrl+C` to stop.

On startup the script prints the active monitor resolution, scale factor, and final ROI so you can verify everything is calibrated correctly before the game loads.

## Notes

- dxcam captures the raw DXGI framebuffer at physical pixels, bypassing Windows DPI scaling. All coordinates in this tool are physical pixels.
- With Windows DPI scaling enabled (e.g. 150% on a 4K display), the physical framebuffer is still 3840×2160 — set `TEMPLATE_BASE_WIDTH` to the physical width, not the logical one.
- Tested on Windows 11 with NVIDIA and AMD GPUs at 1440p and 4K with 150% DPI scaling.