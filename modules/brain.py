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
You are the lead scriptwriter and YouTube SEO expert for a viral Edutainment channel.
Topic: {topic}

Generate SEO metadata and 7-8 fast-paced scenes following this proven retention structure:
- Scene 1: High-impact Hook (Creates instant curiosity in the first 3 seconds)
- Scene 2-4: Core Context & Mind-blowing mechanism
- Scene 5-6: Unexpected Twist or Revelation
- Final Scene: Strong Outro / Punchline

STRICT SCRIPT & VISUAL RULES:
1. "text": Maximum 12-15 words per scene. Punchy, fast-paced narration.
   - ANTI-CLICHÉ HOOK: DO NOT start Scene 1 with overused AI clichés like "What if I told you", "Did you know that", or "Have you ever wondered". Start Scene 1 IMMEDIATELY with a striking fact, year, or high-stakes event.
   - CONCRETE DATA & NUMBERS: Include 2-3 real, specific data points or numbers across the script (e.g. exact depth in feet/meters, yield in kilotons, speed, temperature, or year). Real numbers create high educational authority.
   - FACTUAL INTEGRITY: Do NOT invent fake ending claims, treaty violations, or historical lies. Limit dramatic hyperbole words ('monstrous', 'scariest', 'terrifying')—let the real mind-blowing facts drive the impact.
   - CRITICAL FOR JSON: Do NOT use double quotes (") inside the text field to prevent JSON syntax errors. Use single quotes (') if quoting.
2. "visual_1" & "visual_2": Must be 2 distinct stock video search queries for Pexels.
   - HIGH-IMPACT VISUAL HOOK: Scene 1 visual_1 MUST be an explosive/high-action visual (e.g., "water explosion", "stormy ocean waves", "nuclear explosion") to stop thumb-scrolling instantly.
   - CONTEXT PRECISION: Be hyper-specific to prevent random stock footage (e.g., use "navy battleship ocean" instead of vague "military", use "underwater ocean depth" instead of "deep sea" to avoid aquariums or land explosions).
   - CRITICAL FOR PEXELS API: Use ONLY 1-3 simple, literal, concrete search terms. NEVER use abstract, poetic, or complex metaphors.
3. "metadata":
   - "title": High CTR viral title with emojis under 60 chars.
   - "description": 2-3 sentence engaging YouTube Shorts description.
   - "hashtags": 5 viral hashtags (e.g. "#Shorts #History #Mystery #Science #DidYouKnow").

Return strict JSON object matching this exact few-shot example schema:
{{
  "metadata": {{
    "title": "The Secret Soviet Moon Crash 🚀🌕",
    "description": "Hours before Apollo 11 made history, a secret Soviet probe crashed into the moon. Discover the hidden space race mystery.",
    "hashtags": "#Shorts #Space #History #Mystery #DidYouKnow"
  }},
  "scenes": [
    {{
      "id": 1,
      "text": "In 1969, a secret Soviet moon lander crashed just hours before Apollo 11.",
      "visual_1": "rocket launch night",
      "visual_2": "full moon space",
      "mood": "shocking"
    }}
  ]
}}
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

