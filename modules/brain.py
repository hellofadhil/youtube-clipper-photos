import json
import os

from dotenv import load_dotenv
from google import genai

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
            "Give me 1 specific, viral, and engaging topic for a Short Documentary. "
            "It should be an engaging 'Did you know' fact or intriguing news. "
            "Return ONLY the topic name."
        )
        client = _get_client()
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
        )
        topic = response.text.strip()
        print(f"Selected Topic: {topic}")
        return topic

    def generate_script(self, topic):
        print(f"Writing script for: {topic}...")
        prompt = f"""
You are the lead scriptwriter for a high-retention Edutainment YouTube Shorts channel.
Topic: {topic}

Create 8-9 fast-paced scenes following Hook -> Context -> Mechanism -> Twist -> Outro.
Use third-person narration and no fluff. Every scene must contain two literal,
Pexels-friendly stock-footage search phrases named visual_1 and visual_2.

Return strict JSON only:
[
  {{
    "id": 1,
    "text": "Narration sentence.",
    "visual_1": "literal stock footage query",
    "visual_2": "second literal stock footage query",
    "mood": "intriguing"
  }}
]
"""
        client = _get_client()
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
