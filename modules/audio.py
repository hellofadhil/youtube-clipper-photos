import asyncio
import os

import edge_tts
from mutagen.mp3 import MP3


class AudioEngine:
    def __init__(self, voice="en-US-AvaNeural"):
        self.voice = voice
        self.output_dir = os.path.join(os.getcwd(), "assets", "audio_clips")
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_audio(self, text, output_filename, retries=3):
        """Generate MP3 narration and extract word boundaries for animated captions."""
        output_path = os.path.join(self.output_dir, output_filename)
        ass_filename = output_filename.rsplit(".", 1)[0] + ".ass"
        ass_path = os.path.join(self.output_dir, ass_filename)

        for attempt in range(retries):
            try:
                communicate = edge_tts.Communicate(text, self.voice, rate="+10%")
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
        word_boundaries, ass_path, total_duration, text_fallback="", words_per_group=3
    ):
        """Create a modern YouTube Shorts word-by-word highlighted ASS subtitle file."""
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

        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "ScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Encoding, MarginL, MarginR, MarginV, Alignment, Outline, Shadow\n"
            "Style: Default,Arial,72,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,0,40,40,550,2,4,2\n\n"
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
                    if j == i:
                        formatted_words.append(
                            f"{{\\c&H0000FFFF&}}{w_text}{{\\c&H00FFFFFF&}}"
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

    async def process_script(self, script_data):
        print(f"🎙️ Starting Audio & Subtitle Generation for {len(script_data)} scenes...")
        for scene in script_data:
            scene_id = scene["id"]
            filename = f"voice_{scene_id}.mp3"
            try:
                file_path, word_boundaries, ass_path = await self.generate_audio(
                    scene["text"], filename
                )
                duration = self.get_audio_duration(file_path)
                scene["audio_path"] = file_path
                scene["duration"] = duration

                generated_ass = self.create_ass_subtitles(
                    word_boundaries, ass_path, duration, text_fallback=scene["text"]
                )
                scene["ass_path"] = generated_ass
                print(
                    f"✅ Scene {scene_id}: {duration:.2f}s generated with animated captions."
                )
                await asyncio.sleep(1)
            except Exception as error:
                print(f"❌ Skipping Scene {scene_id} due to audio/subtitle error: {error}")
        return script_data

