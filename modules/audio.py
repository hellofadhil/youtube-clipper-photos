import asyncio
import os
import re
import textwrap

import edge_tts
from mutagen.mp3 import MP3


def optimize_script_text_for_tts(text: str, voice: str) -> str:
    """Pre-process text for natural AI voiceover cadence and dramatic pauses."""
    if not text:
        return text

    clean = re.sub(r"\s+", " ", text).strip()

    if "id-ID" in voice:
        # Enhance Indonesian dramatic storytelling pauses with natural dash/period breaks
        clean = re.sub(
            r"\b(Bayangin|Gokilnya lagi|Gokilnya|Parahnya lagi|Parahnya|Tapi anehnya|Bahkan|Ternyata|Nggak cuma itu|Dan alasannya adalah|Dan alasannya|Tahukah kamu|Tahu nggak)\b(?!\s*[\.,\-\?])",
            r"\1...",
            clean,
            flags=re.IGNORECASE,
        )
        # Format numbers and symbols for natural Indonesian TTS speech
        clean = clean.replace("%", " persen").replace("$", " dollar ").replace("USD", " US Dollar ")

    return clean


class AudioEngine:
    def __init__(self, voice="en-US-AvaNeural", rate="+6%", pitch: str | None = None):
        self.voice = voice
        # Auto-optimize rate & pitch for Indonesian voice for 10/10 podcast/storytelling sound
        if "id-ID" in voice:
            if not rate or rate in ["+0%", "+4%"]:
                rate = "+12%"
            if not pitch:
                pitch = "-2Hz" if "Ardi" in voice else "-1Hz"

        self.rate = os.getenv("TTS_RATE") or rate
        self.pitch = os.getenv("TTS_PITCH") or pitch or "+0Hz"
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_elevenlabs_audio(self, text: str, output_path: str, voice_id: str = "pNInz6obpgDQGcFmaJgB"):
        """Generate 10/10 ultra-realistic human narration using ElevenLabs Multilingual v2 API."""
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not set.")

        import json
        import urllib.request

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key.strip(),
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.80,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            with open(output_path, "wb") as f:
                f.write(content)

        return output_path

    async def generate_audio(self, text, output_filename, retries=3):
        """Generate MP3 narration and extract word boundaries for animated captions."""
        output_path = os.path.join(self.output_dir, output_filename)
        ass_filename = output_filename.rsplit(".", 1)[0] + ".ass"
        ass_path = os.path.join(self.output_dir, ass_filename)

        optimized_text = optimize_script_text_for_tts(text, self.voice)

        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        if elevenlabs_key and elevenlabs_key.strip():
            try:
                print(f"🎙️ Using ElevenLabs 10/10 Humanlike Voiceover API...")
                eleven_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
                file_path = self.generate_elevenlabs_audio(optimized_text, output_path, voice_id=eleven_voice_id)
                return file_path, [], ass_path
            except Exception as el_err:
                print(f"⚠️ ElevenLabs API Error ({el_err}). Falling back to Ultra-Tuned Edge TTS...")

        for attempt in range(retries):
            try:
                communicate = edge_tts.Communicate(optimized_text, self.voice, rate=self.rate, pitch=self.pitch)
                word_boundaries = []

                with open(output_path, "wb") as audio_file:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_file.write(chunk["data"])
                        elif chunk["type"] == "WordBoundary":
                            start_sec = chunk["offset"] / 10_000_000
                            duration_sec = chunk["duration"] / 10_000_000
                            word_boundaries.append(
                                {
                                    "word": chunk["text"],
                                    "start": start_sec,
                                    "end": start_sec + duration_sec,
                                }
                            )

                return output_path, word_boundaries, ass_path
            except Exception as error:
                print(f"⚠️ Audio Error (Attempt {attempt + 1}/{retries}): {error}")
                if attempt < retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise

    @staticmethod
    def get_audio_duration(file_path):
        try:
            return MP3(file_path).info.length
        except Exception as error:
            print(f"❌ Error reading audio length: {error}")
            return 0.0

    @staticmethod
    def create_ass_subtitles(
        word_boundaries, ass_path, total_duration, text_fallback="", words_per_group=2, hook_title="", is_last_scene=False, category_name=""
    ):
        """Create a modern YouTube Shorts smart-highlight ASS subtitle file with optional Top Hook Banner and End Subscribe CTA."""
        if not word_boundaries and text_fallback:
            words = text_fallback.strip().split()
            if words:
                time_per_word = max(0.1, total_duration / len(words))
                word_boundaries = [
                    {
                        "word": w,
                        "start": i * time_per_word,
                        "end": (i + 1) * time_per_word,
                    }
                    for i, w in enumerate(words)
                ]

        if not word_boundaries:
            return None

        # Filter out common stop/filler words from yellow highlighting for a cinematic feel
        STOP_WORDS = {
            "A", "AN", "THE", "AND", "OR", "BUT", "IF", "IN", "ON", "AT",
            "TO", "FOR", "WITH", "BY", "OF", "ITS", "IT", "IS", "WAS",
            "ARE", "WERE", "THAT", "THIS", "AS", "SO", "THAN"
        }

        fontname = os.getenv("SUBTITLE_FONT", "Impact")
        watermark_text = os.getenv("WATERMARK_TEXT", "")

        watermark_style_line = (
            f"Style: Watermark,Arial,34,&H70FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,0,30,30,140,2,2,1\n"
            if watermark_text and watermark_text.strip()
            else ""
        )

        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "ScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Encoding, MarginL, MarginR, MarginV, Alignment, Outline, Shadow\n"
            f"Style: Default,{fontname},76,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,0,90,90,560,2,6,3\n"
            f"Style: HookHeader,{fontname},56,&H0000FFFF,&H00FFFFFF,&H00000000,&H90000000,1,0,0,0,100,100,0,0,3,0,50,50,220,8,5,3\n"
            f"{watermark_style_line}\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        def format_time(seconds):
            hrs = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            centisecs = int(round((seconds % 1) * 100))
            if centisecs >= 100:
                secs += 1
                centisecs = 0
            return f"{hrs}:{mins:02d}:{secs:02d}.{centisecs:02d}"

        events = []

        if watermark_text and watermark_text.strip():
            events.append(
                f"Dialogue: 0,0:00:00.00,{format_time(total_duration)},Watermark,,0,0,0,,{watermark_text.strip()}"
            )

        if hook_title and hook_title.strip():
            clean_hook = hook_title.upper().strip()
            # Dynamic multi-line text wrapping without truncating with '...'
            wrapped_lines = textwrap.wrap(clean_hook, width=28)
            clean_hook_text = "\\N".join(wrapped_lines)

            # Auto font-scaling for long titles to ensure elegant fit on top banner
            font_size_override = "{\\fs44}" if len(clean_hook) > 50 else ("{\\fs48}" if len(clean_hook) > 35 else "")

            hook_end_time = min(3.5, total_duration)
            events.append(
                f"Dialogue: 0,0:00:00.00,{format_time(hook_end_time)},HookHeader,,0,0,0,,{font_size_override}{clean_hook_text}"
            )

        chunks = [
            word_boundaries[i : i + words_per_group]
            for i in range(0, len(word_boundaries), words_per_group)
        ]

        for chunk in chunks:
            if not chunk:
                continue
            group_end = chunk[-1]["end"]

            for i, current_word in enumerate(chunk):
                word_start = current_word["start"]
                word_end = (
                    chunk[i + 1]["start"]
                    if i + 1 < len(chunk)
                    else group_end
                )
                if word_end <= word_start:
                    word_end = word_start + 0.1

                formatted_words = []
                for j, item in enumerate(chunk):
                    w_text = item["word"].upper().replace('"', "").replace("'", "")
                    # Highlight in bright yellow + Kinetic Pop scaling for active word
                    if j == i:
                        formatted_words.append(
                            f"{{\\c&H0000FFFF&\\fscx112\\fscy112}}{w_text}{{\\c&H00FFFFFF&\\fscx100\\fscy100}}"
                        )
                    else:
                        formatted_words.append(w_text)

                line_text = " ".join(formatted_words)
                events.append(
                    f"Dialogue: 0,{format_time(word_start)},{format_time(word_end)},Default,,0,0,0,,{line_text}"
                )

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(header + "\n".join(events) + "\n")

        return ass_path

    async def process_script(self, script_data, bgm_only: bool = False, title: str = "", category_name: str = ""):
        """Process all scenes with optional top hook header for Scene 1."""
        if isinstance(script_data, dict):
            if not title:
                title = script_data.get("metadata", {}).get("title", "")
            script_data = script_data.get("scenes", [])

        if bgm_only:
            print(f"🎵 BGM-Only Mode: Skipping voice & subtitle for {len(script_data)} scenes.")
            for scene in script_data:
                scene["audio_path"] = None
                scene["ass_path"] = None
                scene["duration"] = float(os.getenv("SCENERY_SCENE_DURATION", "4"))
                print(f"  ✅ Scene {scene['id']}: {scene['duration']}s (visual only, no narration)")
            return script_data

        print(f"🎙️ Starting Audio & Subtitle Generation for {len(script_data)} scenes...")
        for scene in script_data:
            scene_id = scene["id"]
            text = scene.get("text", "").strip()

            # Scene-level BGM-only detection: empty text means skip TTS
            if not text:
                scene["audio_path"] = None
                scene["ass_path"] = None
                scene["duration"] = float(os.getenv("SCENERY_SCENE_DURATION", "4"))
                print(f"  🎵 Scene {scene_id}: No narration text — BGM only ({scene['duration']}s).")
                continue

            filename = f"voice_{scene_id}.mp3"
            try:
                file_path, word_boundaries, ass_path = await self.generate_audio(
                    text, filename
                )
                duration = self.get_audio_duration(file_path)
                scene["audio_path"] = file_path
                scene["duration"] = duration

                hook_to_pass = title if scene_id == 1 else ""
                is_last = (scene_id == len(script_data))
                generated_ass = self.create_ass_subtitles(
                    word_boundaries, ass_path, duration, text_fallback=text, hook_title=hook_to_pass, is_last_scene=is_last, category_name=category_name
                )
                scene["ass_path"] = generated_ass
                print(
                    f"✅ Scene {scene_id}: {duration:.2f}s generated with animated captions."
                )
                await asyncio.sleep(1)
            except Exception as error:
                print(f"❌ Skipping Scene {scene_id} due to audio/subtitle error: {error}")
        return script_data
