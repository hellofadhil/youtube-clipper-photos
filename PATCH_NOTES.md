# Patch Notes — Milestone 1

## Avatar removal

In the upstream `modules/composer.py` audited from branch `Main`, remove these
logical blocks:

1. `self.avatar_path = ...` in `Composer.__init__`.
2. The `is_avatar=False` argument from `process_scene`.
3. The full `if is_avatar:` branch containing avatar loop, logo crop, and resize.
4. Avatar index selection in `render_all_scenes`.
5. The block that replaces `current_pair` with `(self.avatar_path, None)`.

The refactored file accepts only stock-footage pairs and has no avatar state,
path, condition, or fallback.

## Why the old graph crashed

The upstream A/B streams were scaled and assigned an FPS, but they retained
other source-dependent link properties. FFmpeg concat/xfade requires matching
video parameters. Two Pexels files can differ in SAR, pixel format, time base,
frame-rate mode, or actual scaled geometry; any one difference can trigger:

```text
Failed to configure output pad on Parsed_concat
Input link parameters do not match
```

## New normalization pipeline

Each clip is encoded independently before entering concat:

```text
loop -> trim -> setpts=PTS-STARTPTS
     -> scale(force_original_aspect_ratio=increase)
     -> crop(1080:1920)
     -> setsar=1
     -> fps=30
     -> format=yuv420p
     -> H.264 MP4, no audio
```

Immediately before concat/xfade, streams are guarded again with fixed scale,
crop, SAR, FPS, pixel format, `settb=AVTB`, and reset PTS. Scene audio is also
converted to 48 kHz stereo before acrossfade.

## Trade-off

This approach performs an extra encode for every stock clip. It is slower than
a single giant filter graph, but substantially easier to debug and far more
reliable for heterogeneous API-provided footage.

## FFmpeg 7.x xfade detail

During the smoke test, placing `setpts` immediately before `xfade` caused
FFmpeg 7.1 to expose a synthetic `1/0` frame-rate value even though the MP4
input was CFR. The final transition path therefore keeps scene files starting
at zero from their prior render, then applies `scale/crop/setsar/format/fps`
without another `setpts`. This was validated end-to-end by the included test.
