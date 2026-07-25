from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Iterable, Sequence

import ffmpeg


class Composer:
    """Render normalized 9:16 scenes and stitch them with safe transitions.

    Every source clip is physically normalized before it is allowed into a
    concat/xfade graph. This intentionally costs one extra encode per source
    clip, but it removes the most common FFmpeg failures caused by mixed SAR,
    time bases, frame rates, dimensions, and pixel formats.
    """

    TARGET_WIDTH = 1080
    TARGET_HEIGHT = 1920
    TARGET_FPS = 30
    AUDIO_SAMPLE_RATE = 48_000

    def __init__(
        self,
        *,
        target_width: int = TARGET_WIDTH,
        target_height: int = TARGET_HEIGHT,
        target_fps: int = TARGET_FPS,
        transition_duration: float = 0.5,
        keep_normalized_clips: bool = False,
    ) -> None:
        self.temp_dir = Path.cwd() / "assets" / "temp"
        self.final_dir = Path.cwd() / "assets" / "final"
        self.normalized_dir = self.temp_dir / "normalized"

        self.target_width = int(target_width)
        self.target_height = int(target_height)
        self.target_fps = int(target_fps)
        self.transition_duration = max(0.0, float(transition_duration))
        self.keep_normalized_clips = keep_normalized_clips

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.final_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

        self.transitions = ["fade", "diagbr", "diagtl"]

    @staticmethod
    def _error_text(error: ffmpeg.Error) -> str:
        stderr = getattr(error, "stderr", None)
        if isinstance(stderr, bytes):
            return stderr.decode("utf-8", errors="replace")
        return str(stderr or error)

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def get_duration(self, filepath: os.PathLike[str] | str) -> float:
        try:
            probe = ffmpeg.probe(str(filepath))
            return float(probe["format"]["duration"])
        except (ffmpeg.Error, KeyError, TypeError, ValueError, OSError):
            return 0.0

    def _video_filters(self, stream):
        """Return a graph with deterministic video link parameters."""
        return (
            stream
            .filter(
                "scale",
                self.target_width,
                self.target_height,
                force_original_aspect_ratio="increase",
                flags="lanczos",
            )
            .filter("crop", self.target_width, self.target_height)
            .filter("setsar", "1")
            .filter("fps", fps=self.target_fps, round="up")
            .filter("format", "yuv420p")
        )

    def normalize_clip(
        self,
        input_path: os.PathLike[str] | str,
        output_path: os.PathLike[str] | str,
        duration: float,
    ) -> Path:
        """Loop, trim, scale, crop, and normalize one stock clip.

        The generated intermediate is always:
        - target_width x target_height
        - SAR 1:1
        - constant target_fps
        - yuv420p
        - H.264 with a deterministic track time scale
        - no audio stream
        """
        source_path = Path(input_path)
        destination = Path(output_path)
        duration = max(0.05, float(duration))

        if not source_path.is_file():
            raise FileNotFoundError(f"Video source not found: {source_path}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        self._safe_unlink(destination)

        source = ffmpeg.input(str(source_path), stream_loop=-1)
        video = (
            source.video
            .filter("trim", duration=duration)
            .filter("setpts", "PTS-STARTPTS")
        )
        video = self._video_filters(video)

        command = (
            ffmpeg
            .output(
                video,
                str(destination),
                vcodec="libx264",
                preset="veryfast",
                crf=18,
                pix_fmt="yuv420p",
                r=self.target_fps,
                an=None,
                movflags="+faststart",
                video_track_timescale=self.target_fps * 1000,
            )
            .global_args("-hide_banner", "-loglevel", "error")
        )

        try:
            command.run(
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True,
            )
        except ffmpeg.Error as error:
            raise RuntimeError(
                f"Could not normalize '{source_path}':\n{self._error_text(error)}"
            ) from error

        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg created an invalid normalized clip: {destination}")

        return destination

    def _prepared_video_input(self, input_node):
        """Final guard before concat/xfade, even for pre-normalized files."""
        stream = self._video_filters(input_node.video)
        return (
            stream
            .filter("settb", "AVTB")
            .filter("setpts", f"N/({self.target_fps}*TB)")
            .filter("setsar", "1")
        )

    def _prepared_transition_video_input(self, input_node):
        """Normalize xfade inputs without setpts/settb.

        FFmpeg 7.x may report a synthetic 1/0 frame rate when setpts is placed
        directly before xfade. Scene MP4 files already start at zero, so xfade
        only needs deterministic geometry, SAR, pixel format, and CFR here.
        """
        return (
            input_node.video
            .filter(
                "scale",
                self.target_width,
                self.target_height,
                force_original_aspect_ratio="increase",
                flags="lanczos",
            )
            .filter("crop", self.target_width, self.target_height)
            .filter("setsar", "1")
            .filter("format", "yuv420p")
            .filter("fps", fps=self.target_fps, round="up")
        )

    def _prepared_audio_input(self, input_node):
        return (
            input_node.audio
            .filter("aresample", self.AUDIO_SAMPLE_RATE)
            .filter(
                "aformat",
                sample_fmts="fltp",
                sample_rates=self.AUDIO_SAMPLE_RATE,
                channel_layouts="stereo",
            )
            .filter("asetpts", "PTS-STARTPTS")
        )

    def process_scene(self, scene: dict, video_pair: Sequence[str | None]) -> str | None:
        """Render one narration scene using stock footage only.

        Avatar injection was deliberately removed. Missing A/B entries heal by
        reusing whichever clip is available.
        """
        scene_id = scene["id"]
        audio_path = Path(scene["audio_path"])
        total_duration = max(0.1, float(scene["duration"]))
        output_path = self.temp_dir / f"scene_{scene_id}.mp4"

        if not audio_path.is_file():
            print(f"❌ Scene {scene_id}: audio missing: {audio_path}")
            return None

        if not video_pair:
            print(f"❌ Scene {scene_id}: no stock footage pair supplied.")
            return None

        path_a = video_pair[0] if len(video_pair) >= 1 else None
        path_b = video_pair[1] if len(video_pair) >= 2 else None
        path_a = path_a or path_b
        path_b = path_b or path_a

        if not path_a or not path_b:
            print(f"❌ Scene {scene_id}: both stock footage clips are missing.")
            return None

        duration_a = total_duration / 2.0
        duration_b = total_duration - duration_a
        normalized_a = self.normalized_dir / f"scene_{scene_id}_a.mp4"
        normalized_b = self.normalized_dir / f"scene_{scene_id}_b.mp4"

        try:
            print(f"⚙️ Processing Scene {scene_id}: normalized A/B stock footage")
            self.normalize_clip(path_a, normalized_a, duration_a)
            self.normalize_clip(path_b, normalized_b, duration_b)

            input_a = ffmpeg.input(str(normalized_a))
            input_b = ffmpeg.input(str(normalized_b))
            stream_a = self._prepared_video_input(input_a)
            stream_b = self._prepared_video_input(input_b)
            video_stream = ffmpeg.concat(stream_a, stream_b, v=1, a=0)

            ass_path = scene.get("ass_path")
            if ass_path and Path(ass_path).is_file():
                escaped_ass = str(Path(ass_path).resolve()).replace("\\", "/").replace(":", "\\:")
                video_stream = video_stream.filter("subtitles", filename=escaped_ass)

            input_audio = ffmpeg.input(str(audio_path))
            audio_stream = self._prepared_audio_input(input_audio)

            self._safe_unlink(output_path)
            command = (
                ffmpeg
                .output(
                    video_stream,
                    audio_stream,
                    str(output_path),
                    vcodec="libx264",
                    acodec="aac",
                    preset="veryfast",
                    crf=18,
                    pix_fmt="yuv420p",
                    r=self.target_fps,
                    ar=self.AUDIO_SAMPLE_RATE,
                    ac=2,
                    shortest=None,
                    movflags="+faststart",
                    video_track_timescale=self.target_fps * 1000,
                )
                .global_args("-hide_banner", "-loglevel", "error")
            )
            command.run(
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True,
            )
            return str(output_path)
        except (ffmpeg.Error, RuntimeError, OSError, ValueError) as error:
            message = self._error_text(error) if isinstance(error, ffmpeg.Error) else str(error)
            print(f"❌ Render Fail Scene {scene_id}: {message}")
            return None
        finally:
            if not self.keep_normalized_clips:
                self._safe_unlink(normalized_a)
                self._safe_unlink(normalized_b)

    def render_all_scenes(
        self,
        script_data: Iterable[dict],
        video_pairs: Sequence[Sequence[str | None] | None],
    ) -> list[str]:
        """Render every scene without any avatar replacement logic."""
        rendered_paths: list[str] = []

        for index, scene in enumerate(script_data):
            if index >= len(video_pairs):
                print(f"❌ Scene {scene.get('id', index + 1)}: video pair is missing.")
                continue

            current_pair = video_pairs[index]
            if current_pair is None:
                print(f"❌ Scene {scene.get('id', index + 1)}: no visual asset available.")
                continue

            output_path = self.process_scene(scene, current_pair)
            if output_path:
                rendered_paths.append(output_path)

        return rendered_paths

    def concatenate_with_transitions(
        self,
        video_paths: Sequence[str],
        output_filename: str = "final_short.mp4",
    ) -> str | None:
        """Stitch normalized scenes using xfade/acrossfade safely."""
        print("🎞️ Stitching final video...")
        output_path = self.final_dir / output_filename
        self._safe_unlink(output_path)

        existing_paths = [Path(path) for path in video_paths if Path(path).is_file()]
        if not existing_paths:
            return None

        first_input = ffmpeg.input(str(existing_paths[0]))
        video_stream = self._prepared_transition_video_input(first_input)
        audio_stream = self._prepared_audio_input(first_input)
        current_duration = self.get_duration(existing_paths[0])

        for index, next_path in enumerate(existing_paths[1:], start=1):
            next_duration = self.get_duration(next_path)
            if current_duration <= 0 or next_duration <= 0:
                print(f"⚠️ Skipping invalid scene during stitch: {next_path}")
                continue

            next_input = ffmpeg.input(str(next_path))
            next_video = self._prepared_transition_video_input(next_input)
            next_audio = self._prepared_audio_input(next_input)

            transition_duration = min(
                self.transition_duration,
                current_duration / 2.0,
                next_duration / 2.0,
            )
            transition_duration = max(0.05, transition_duration)
            offset = max(0.0, current_duration - transition_duration)
            effect = random.choice(self.transitions)

            print(
                f"✨ Transition {index}: '{effect}' "
                f"duration={transition_duration:.2f}s offset={offset:.2f}s"
            )

            video_stream = ffmpeg.filter(
                [video_stream, next_video],
                "xfade",
                transition=effect,
                duration=transition_duration,
                offset=offset,
            )
            video_stream = (
                video_stream
                .filter("setsar", "1")
                .filter("format", "yuv420p")
            )
            audio_stream = ffmpeg.filter(
                [audio_stream, next_audio],
                "acrossfade",
                d=transition_duration,
            )
            current_duration = current_duration + next_duration - transition_duration

        command = (
            ffmpeg
            .output(
                video_stream,
                audio_stream,
                str(output_path),
                vcodec="libx264",
                acodec="aac",
                preset="medium",
                crf=18,
                pix_fmt="yuv420p",
                r=self.target_fps,
                ar=self.AUDIO_SAMPLE_RATE,
                ac=2,
                movflags="+faststart",
                video_track_timescale=self.target_fps * 1000,
            )
            .global_args("-hide_banner", "-loglevel", "error")
        )

        try:
            command.run(
                overwrite_output=True,
                capture_stdout=True,
                capture_stderr=True,
            )
            print(f"✅ FINAL VIDEO SAVED: {output_path}")
            return str(output_path)
        except ffmpeg.Error as error:
            print(f"❌ Stitching Error: {self._error_text(error)}")
            return None
