# AutoShorts AI — FFmpeg Stability Refactor

This package is a refactored snapshot of `SaarD00/AI-Youtube-Shorts-Generator`
focused on the first requested milestone: remove avatar injection and fix mixed
resolution/SAR/FPS crashes in FFmpeg.

## What changed

- Avatar injection was fully removed from `modules/composer.py`.
- Every Pexels clip is pre-rendered into a normalized intermediate before concat:
  - `1080x1920`
  - center-cropped after aspect-ratio-preserving upscale
  - `setsar=1`
  - constant `30fps`
  - `yuv420p`
  - H.264 with deterministic video track timescale
- Scene video and audio are normalized again immediately before `concat`, `xfade`,
  and `acrossfade` as a defensive guard.
- Narration audio is standardized to stereo AAC at 48 kHz.
- A reproducible smoke test intentionally combines SAR `1:1` and `32:27`, plus
  different resolutions and frame rates.

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Install FFmpeg and ensure both `ffmpeg` and `ffprobe` are available in `PATH`.
Copy `.env.example` to `.env`, then fill in Gemini and Pexels API keys.

## Run

### Option 1: Web Studio (GUI Dashboard)

```bash
python web_app.py
```

### Option 2: CLI Automation

```bash
python main.py
```

## Verify the FFmpeg fix

```bash
python tools/smoke_test_composer.py
```

Expected final stream properties:

```text
width=1080
height=1920
sample_aspect_ratio=1:1
pix_fmt=yuv420p
r_frame_rate=30/1
```

See `PATCH_NOTES.md` for the exact removed blocks and technical rationale.
