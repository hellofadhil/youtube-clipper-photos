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
        """Generate MP3 narration with retry handling."""
        output_path = os.path.join(self.output_dir, output_filename)
        for attempt in range(retries):
            try:
                communicate = edge_tts.Communicate(text, self.voice, rate="+10%")
                await communicate.save(output_path)
                return output_path
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

    async def process_script(self, script_data):
        print(f"🎙️ Starting Audio Generation for {len(script_data)} scenes...")
        for scene in script_data:
            scene_id = scene["id"]
            filename = f"voice_{scene_id}.mp3"
            try:
                file_path = await self.generate_audio(scene["text"], filename)
                duration = self.get_audio_duration(file_path)
                scene["audio_path"] = file_path
                scene["duration"] = duration
                print(f"✅ Scene {scene_id}: {duration:.2f}s generated.")
                await asyncio.sleep(1)
            except Exception:
                print(f"❌ Skipping Scene {scene_id} due to audio error.")
        return script_data
