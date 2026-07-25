"""Generate deliberately mismatched clips and verify the Composer end-to-end."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.composer import Composer


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main() -> int:
    root = Path.cwd()
    fixture_dir = root / "assets" / "smoke_fixtures"
    audio_dir = root / "assets" / "audio_clips"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    clip_a = fixture_dir / "sar_1_1_24fps.mp4"
    clip_b = fixture_dir / "sar_32_27_25fps.mp4"
    audio_1 = audio_dir / "smoke_1.wav"
    audio_2 = audio_dir / "smoke_2.wav"

    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "testsrc2=size=720x1280:rate=24:duration=1.6",
        "-vf", "setsar=1/1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip_a),
    ])
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "testsrc2=size=720x576:rate=25:duration=1.6",
        "-vf", "setsar=32/27", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip_b),
    ])
    for output, frequency in [(audio_1, "440"), (audio_2, "660")]:
        run([
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            f"sine=frequency={frequency}:sample_rate=44100:duration=1.4",
            "-ac", "1", str(output),
        ])

    scenes = [
        {"id": 1, "audio_path": str(audio_1), "duration": 1.4},
        {"id": 2, "audio_path": str(audio_2), "duration": 1.4},
    ]
    pairs = [(str(clip_a), str(clip_b)), (str(clip_b), str(clip_a))]

    composer = Composer(transition_duration=0.25)
    scene_paths = composer.render_all_scenes(scenes, pairs)
    if len(scene_paths) != 2:
        raise RuntimeError(f"Expected two rendered scenes, got: {scene_paths}")

    final_path = composer.concatenate_with_transitions(
        scene_paths,
        output_filename="smoke_test_final.mp4",
    )
    if not final_path or not Path(final_path).is_file():
        raise RuntimeError("Final smoke-test video was not created")

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,sample_aspect_ratio,pix_fmt",
            "-of", "default=noprint_wrappers=1", final_path,
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    print(probe.stdout.strip())
    print(f"SMOKE TEST PASSED: {final_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
