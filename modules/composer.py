from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
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
        self.max_workers = int(os.getenv("MAX_CONCURRENT_WORKERS", "7"))
        env_vcodec = os.getenv("FFMPEG_VCODEC")
        if env_vcodec:
            self.vcodec = env_vcodec
            if self.vcodec != "libx264" and not self._is_vcodec_available(self.vcodec):
                print(f"⚠️ GPU/Encoder '{self.vcodec}' is not supported by FFmpeg binary or hardware. Falling back to 'libx264' (CPU).")
                self.vcodec = "libx264"
            elif self.vcodec != "libx264":
                print(f"⚡ Hardware Acceleration Active: Using '{self.vcodec}' encoder.")
        else:
            if self._is_vcodec_available("h264_nvenc"):
                self.vcodec = "h264_nvenc"
                print("⚡ NVIDIA T4 GPU Auto-Detected: Hardware Acceleration Active ('h264_nvenc').")
            else:
                self.vcodec = "libx264"

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.final_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

        self.transitions = ["fade", "diagbr", "diagtl"]

    @staticmethod
    def _is_vcodec_available(vcodec: str) -> bool:
        """Probe FFmpeg to check if a specific encoder (e.g. h264_nvenc) is usable."""
        if not vcodec or vcodec == "libx264":
            return True

        preset_candidates = ["fast", "p4", "p1", None] if "nvenc" in vcodec.lower() else [None]
        for preset_opt in preset_candidates:
            try:
                extra_opts = {}
                if preset_opt:
                    extra_opts["preset"] = preset_opt

                command = (
                    ffmpeg
                    .input("color=c=black:s=100x100:d=0.1", format="lavfi")
                    .output("pipe:", format="null", vcodec=vcodec, pix_fmt="yuv420p", **extra_opts)
                    .global_args("-hide_banner", "-loglevel", "error")
                )
                command.run(capture_stdout=True, capture_stderr=True)
                return True
            except Exception:
                continue
        return False

    def _get_vcodec_options(self) -> dict:
        """Return optimal codec options for CPU (libx264) or GPU (nvenc, qsv, videotoolbox)."""
        options = {
            "vcodec": self.vcodec,
            "pix_fmt": "yuv420p",
            "r": self.target_fps,
            "movflags": "+faststart",
            "video_track_timescale": self.target_fps * 1000,
        }
        vcodec_lower = self.vcodec.lower()
        if "nvenc" in vcodec_lower:
            options["preset"] = "fast"
            options["cq"] = 18
        elif "qsv" in vcodec_lower:
            options["preset"] = "veryfast"
            options["global_quality"] = 18
        elif "videotoolbox" in vcodec_lower:
            options["q"] = 60
        else:
            options["preset"] = "veryfast"
            options["crf"] = 18
        return options

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

        output_opts = self._get_vcodec_options()
        output_opts["an"] = None

        command = (
            ffmpeg
            .output(
                video,
                str(destination),
                **output_opts,
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
            .filter("loudnorm", I=-16, TP=-1.5, LRA=11)
            .filter("asetpts", "PTS-STARTPTS")
        )

    def process_scene(self, scene: dict, video_pair: Sequence[str | None]) -> str | None:
        """Render one narration scene using stock footage only.

        Supports two modes:
        - Standard: narration voice (audio_path) + optional animated subtitles (ass_path).
        - BGM-only: audio_path is None; a silent audio track is generated so the
          scene MP4 is still valid. Background music is mixed in later during stitch.
        """
        scene_id = scene["id"]
        audio_path = scene.get("audio_path")
        if audio_path:
            audio_path = Path(audio_path)
        total_duration = max(0.1, float(scene["duration"]))
        output_path = self.temp_dir / f"scene_{scene_id}.mp4"

        bgm_only = audio_path is None

        if not bgm_only and not audio_path.is_file():
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
            print(f"⚙️ Processing Scene {scene_id}: parallel clip normalization (A/B)")
            with ThreadPoolExecutor(max_workers=2) as executor:
                fut_a = executor.submit(self.normalize_clip, path_a, normalized_a, duration_a)
                fut_b = executor.submit(self.normalize_clip, path_b, normalized_b, duration_b)
                fut_a.result()
                fut_b.result()

            input_a = ffmpeg.input(str(normalized_a))
            input_b = ffmpeg.input(str(normalized_b))
            stream_a = self._prepared_video_input(input_a)
            stream_b = self._prepared_video_input(input_b)
            video_stream = ffmpeg.concat(stream_a, stream_b, v=1, a=0)

            ass_path = scene.get("ass_path")
            if ass_path and Path(ass_path).is_file():
                escaped_ass = str(Path(ass_path).resolve()).replace("\\", "/").replace(":", "\\:")
                video_stream = video_stream.filter("subtitles", filename=escaped_ass)

            # Build audio stream: real narration or a silent tone for BGM-only scenes
            if bgm_only:
                # Generate a silent audio stream matching scene duration
                audio_stream = (
                    ffmpeg
                    .input(
                        "anullsrc=channel_layout=stereo:sample_rate=48000",
                        format="lavfi",
                        t=total_duration,
                    )
                    .audio
                    .filter("aresample", self.AUDIO_SAMPLE_RATE)
                    .filter(
                        "aformat",
                        sample_fmts="fltp",
                        sample_rates=self.AUDIO_SAMPLE_RATE,
                        channel_layouts="stereo",
                    )
                )
            else:
                input_audio = ffmpeg.input(str(audio_path))
                audio_stream = self._prepared_audio_input(input_audio)

            self._safe_unlink(output_path)
            scene_opts = self._get_vcodec_options()
            scene_opts.update({
                "acodec": "aac",
                "ar": self.AUDIO_SAMPLE_RATE,
                "ac": 2,
                "shortest": None,
            })

            command = (
                ffmpeg
                .output(
                    video_stream,
                    audio_stream,
                    str(output_path),
                    **scene_opts,
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
        """Render scenes in parallel using ThreadPoolExecutor."""
        script_list = list(script_data)
        tasks = []

        for index, scene in enumerate(script_list):
            if index >= len(video_pairs):
                print(f"❌ Scene {scene.get('id', index + 1)}: video pair is missing.")
                continue

            current_pair = video_pairs[index]
            if current_pair is None:
                print(f"❌ Scene {scene.get('id', index + 1)}: no visual asset available.")
                continue

            tasks.append((index, scene, current_pair))

        if not tasks:
            return []

        max_workers = max(1, min(self.max_workers, len(tasks)))
        print(f"⚡ Parallel rendering {len(tasks)} scene(s) with {max_workers} thread worker(s)...")

        rendered_paths: list[str | None] = [None] * len(script_list)

        def worker(idx: int, sc: dict, pair: Sequence[str | None]):
            path = self.process_scene(sc, pair)
            return idx, path

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(worker, idx, sc, pair)
                for idx, sc, pair in tasks
            ]
            for future in as_completed(futures):
                try:
                    idx, path = future.result()
                    if path:
                        rendered_paths[idx] = path
                except Exception as error:
                    print(f"❌ Parallel render error: {error}")

        return [p for p in rendered_paths if p is not None]

    def concatenate_with_transitions(
        self,
        video_paths: Sequence[str],
        output_filename: str = "final_short.mp4",
        bgm_mood: str | None = None,
    ) -> str | None:
        """Stitch normalized scenes using xfade/acrossfade safely.

        Args:
            video_paths: Ordered list of rendered scene MP4 paths.
            output_filename: Name of the output file inside assets/final/.
            bgm_mood: Optional BGM genre subfolder name (e.g. 'cinematic', 'lofi',
                      'tropical'). When provided the composer looks in
                      assets/bgm/{bgm_mood}/ first, then falls back to assets/bgm/.
        """
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

        # ── BGM selection & Sidechain Ducking ─────────────────────────────────
        bgm_dir = Path.cwd() / "assets" / "bgm"
        bgm_files: list[Path] = []

        if bgm_mood:
            mood_dir = bgm_dir / bgm_mood
            if mood_dir.is_dir():
                bgm_files = list(mood_dir.glob("*.mp3")) + list(mood_dir.glob("*.wav"))
                if bgm_files:
                    print(f"🎵 BGM Mood: '{bgm_mood}' — found {len(bgm_files)} track(s) in {mood_dir.name}/")

        if not bgm_files and bgm_dir.is_dir():
            bgm_files = list(bgm_dir.glob("*.mp3")) + list(bgm_dir.glob("*.wav"))
            if bgm_files:
                print(f"🎵 BGM Mood fallback: using root assets/bgm/ ({len(bgm_files)} track(s))")

        if bgm_files:
            bgm_path = random.choice(bgm_files)
            print(f"🎵 Mixing BGM with Sidechain Audio Ducking: {bgm_path.name}")
            bgm_input = (
                ffmpeg.input(str(bgm_path), stream_loop=-1)
                .audio
                .filter("volume", 0.18)
                .filter("atrim", duration=current_duration)
                .filter("aresample", self.AUDIO_SAMPLE_RATE)
                .filter(
                    "aformat",
                    sample_fmts="fltp",
                    sample_rates=self.AUDIO_SAMPLE_RATE,
                    channel_layouts="stereo",
                )
            )
            # Sidechaincompress dynamically lowers BGM volume when narrator speaks
            try:
                bgm_ducked = ffmpeg.filter(
                    [bgm_input, audio_stream],
                    "sidechaincompress",
                    threshold=0.06,
                    ratio=4,
                    attack=15,
                    release=250,
                )
                audio_stream = ffmpeg.filter([audio_stream, bgm_ducked], "amix", inputs=2, duration="first")
            except Exception:
                audio_stream = ffmpeg.filter([audio_stream, bgm_input], "amix", inputs=2, duration="first")

            audio_stream = audio_stream.filter("loudnorm", I=-16, TP=-1.5, LRA=11)
        else:
            print("⚠️ No BGM files found. Add .mp3/.wav files to assets/bgm/ or assets/bgm/{mood}/ to enable background music.")

        command = (
            ffmpeg
            .output(
                video_stream,
                audio_stream,
                str(output_path),
                vcodec=self.vcodec,
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

    def generate_preview(
        self,
        input_video_path: str,
        output_filename: str = "final_short_preview.mp4",
    ) -> str | None:
        """Generate an ultra-compressed 360x640 preview video (~1.5 MB) for low-bandwidth streaming in Colab."""
        output_path = self.final_dir / output_filename
        self._safe_unlink(output_path)

        try:
            print("⚡ Generating Ultra-Stream Low-Bandwidth Preview (~1.5 MB)...")
            inp = ffmpeg.input(input_video_path)
            video = (
                inp.video
                .filter("scale", 360, 640)
                .filter("format", "yuv420p")
            )
            audio = inp.audio

            command = (
                ffmpeg
                .output(
                    video,
                    audio,
                    str(output_path),
                    vcodec=self.vcodec,
                    acodec="aac",
                    preset="ultrafast",
                    crf=28,
                    b="400k",
                    movflags="+faststart",
                )
                .global_args("-hide_banner", "-loglevel", "error")
            )
            command.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            print(f"✅ PREVIEW GENERATED: {output_path}")
            return str(output_path)
        except Exception as error:
            print(f"⚠️ Preview Generation Warning: {error}")
            return None
