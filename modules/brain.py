import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Create a .env file or set the environment variable before running."
        )
    return genai.Client(api_key=api_key)


class ContentBrain:
    def get_trending_topic(self):
        prompt = (
            "Give me 1 highly engaging, mind-blowing, and specific topic for an edutainment YouTube Short. "
            "Focus on high-retention categories like: Dark History, Mind-Blowing Science, Deep Space, or Unexplained Mysteries. "
            "The topic must instantly spark curiosity for a Gen Z/Millennial audience. "
            "Frame the topic as a hidden secret, intrigue, or gripping mystery (e.g., 'The Lost Soviet Space Mission', not generic 'History of Soviet Space'). "
            "Return ONLY the topic title, without any quotes or commentary."
        )
        client = _get_client()
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
        )
        topic = response.text.strip().strip('"').strip("'")
        print(f"Selected Topic: {topic}")
        return topic

    def generate_script(self, topic):
        print(f"Writing script for: {topic}...")
        prompt = f"""
You are the lead scriptwriter for a viral, high-retention Edutainment YouTube Shorts channel.
Topic: {topic}

Create 7-8 fast-paced scenes following this proven retention structure:
- Scene 1: High-impact Hook (Creates instant curiosity in the first 3 seconds)
- Scene 2-4: Core Context & Mind-blowing mechanism
- Scene 5-6: Unexpected Twist or Revelation
- Final Scene: Strong Outro / Punchline

STRICT SCRIPT & VISUAL RULES:
1. "text": Maximum 12-15 words per scene. Punchy, fast-paced narration.
   - CONCRETE DATA & NUMBERS: Include 2-3 real, specific data points or numbers across the script (e.g. exact depth in feet/meters, yield in kilotons, speed, temperature, or year). Real numbers create high educational authority.
   - FACTUAL INTEGRITY: Do NOT invent fake ending claims, treaty violations, or historical lies. Limit dramatic hyperbole words ('monstrous', 'scariest', 'terrifying')—let the real mind-blowing facts drive the impact.
   - CRITICAL FOR JSON: Do NOT use double quotes (") inside the text field to prevent JSON syntax errors. Use single quotes (') if quoting.
2. "visual_1" & "visual_2": Must be 2 distinct stock video search queries for Pexels.
   CRITICAL FOR PEXELS API: Use ONLY 1-3 simple, literal, concrete search terms (e.g., "galaxy space", "ancient pyramid", "scared face close up", "neon city night"). NEVER use abstract, poetic, or complex metaphors.

Return strict JSON array matching this exact few-shot example schema:
[
  {{
    "id": 1,
    "text": "What if I told you the moon is slowly drifting away from us?",
    "visual_1": "full moon night",
    "visual_2": "space galaxy",
    "mood": "mysterious"
  }}
]
"""
        client = _get_client()
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )
            clean_text = response.text.strip()
            return json.loads(clean_text)
        except Exception as error:
            print(f"⚠️ Primary JSON generation issue: {error}. Falling back to standard mode...")
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=prompt,
            )
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(clean_text)
            except json.JSONDecodeError:
                print("❌ Error parsing JSON. Raw output:")
                print(clean_text)
                return None

