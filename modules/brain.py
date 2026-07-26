import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Topic categories available for content generation
# ─────────────────────────────────────────────────────────────────────────────
TOPIC_CATEGORIES = {
    "1": {
        "name": "🌍 Dark History",
        "description": "Sejarah kelam & misteri masa lalu",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 highly engaging, specific topic for a viral Dark History YouTube Short. "
            "Focus on: real covert government operations, shocking war crimes that were covered up, "
            "secret experiments on civilians, powerful empires that collapsed overnight, or forgotten genocides. "
            "The topic MUST sound like a classified document was just declassified. "
            "Examples of the RIGHT style: 'The CIA Mind-Control Experiment That Drove 80 People Insane', "
            "'The 3-Day Atomic Bomb Test on US Soldiers', 'The Nazi Gold Train Still Buried Under Poland'. "
            "Examples of the WRONG style: 'A History of Wars', 'Dark Moments in History'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "DARK HISTORY VISUAL RULES:\n"
            "- Scene 1 HOOK must use high-impact war/explosion footage: 'battlefield explosion smoke', "
            "'nuclear bomb explosion', 'warship fire ocean'.\n"
            "- For government/spy topics use: 'government building', 'classified documents desk', 'old newspaper headline'.\n"
            "- For war scenes use: 'soldiers trench war', 'tank battlefield', 'army march'.\n"
            "- For experiments use: 'laboratory old equipment', 'hospital corridor dark', 'scientist lab'.\n"
            "- For empires/ruins: 'ancient ruins stone', 'crumbling castle', 'abandoned city overgrown'.\n"
            "- ALWAYS prefer dramatic, high-contrast, dark-toned footage queries."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "The CIA Experiment That Destroyed 80 Minds 🕵️",
    "description": "In 1953, the CIA secretly drugged 80 unwitting civilians with LSD for 10 years. Project MKUltra was the darkest chapter of American history.",
    "hashtags": "#Shorts #DarkHistory #CIA #Conspiracy #DidYouKnow"
  },
  "scenes": [
    {
      "id": 1,
      "text": "In 1953, the CIA secretly dosed 80 people with LSD without consent.",
      "visual_1": "nuclear explosion black white",
      "visual_2": "classified documents desk lamp",
      "mood": "shocking"
    }
  ]
}""",
    },
    "2": {
        "name": "🔬 Mind-Blowing Science",
        "description": "Fakta sains yang bikin otak meledak",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 mind-blowing, counterintuitive science topic for a viral YouTube Short. "
            "Focus on: paradoxes that break common sense, recent discoveries that overturned textbooks, "
            "extreme physics or biology facts with real measurable numbers, or simulations of reality. "
            "The topic MUST feel like it challenges everything the viewer thought they knew. "
            "Examples of the RIGHT style: 'Your Body Replaces 98% of Its Atoms Every Year — You Are Not The Same Person', "
            "'The Double Slit Experiment Proves Reality Only Exists When Observed', "
            "'A Teaspoon of Neutron Star Weighs 10 Million Tons'. "
            "Examples of the WRONG style: 'Interesting Science Facts', 'How Quantum Physics Works'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "MIND-BLOWING SCIENCE VISUAL RULES:\n"
            "- Scene 1 HOOK: use visually striking macro or cosmic footage: 'cell division microscope', "
            "'atom particle collision', 'lightning strike slow motion', 'lava flow close up'.\n"
            "- For brain/biology topics: 'human brain anatomy', 'neurons firing closeup', 'blood cells microscope'.\n"
            "- For physics: 'laser beam laboratory', 'magnetic field visualization', 'particle accelerator'.\n"
            "- For space physics: 'sun solar flare', 'star explosion supernova', 'galaxy spiral'.\n"
            "- For chemistry: 'chemical reaction colored liquid', 'laboratory test tube', 'explosion chemical'.\n"
            "- AVOID: abstract/poetic queries like 'mind expanding'. Use LITERAL visual descriptions only."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "A Teaspoon of Neutron Star = 10 Million Tons 🤯⭐",
    "description": "Neutron stars are the densest objects in the universe. Just one teaspoon of their matter weighs more than all of humanity combined.",
    "hashtags": "#Shorts #Science #MindBlown #Physics #DidYouKnow"
  },
  "scenes": [
    {
      "id": 1,
      "text": "A teaspoon of neutron star material weighs 10 million tons.",
      "visual_1": "star explosion supernova",
      "visual_2": "galaxy deep space",
      "mood": "shocking"
    }
  ]
}""",
    },
    "3": {
        "name": "🌌 Deep Space & Cosmos",
        "description": "Misteri galaksi, black hole, dan alam semesta",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 awe-inspiring, fear-inducing cosmic topic for a viral Deep Space YouTube Short. "
            "Focus on: scale of the universe that makes humans feel insignificant, black hole behavior, "
            "alien planet extreme conditions with real data, cosmic events that could end Earth, "
            "or unsolved radio signals from deep space. "
            "The topic MUST use specific real astronomical data (distances in light-years, temperatures, sizes). "
            "Examples of the RIGHT style: 'The Void 330 Million Light-Years Wide With Nothing Inside', "
            "'A Rogue Planet 7x Jupiter's Mass Is Heading Through Our Galaxy', "
            "'The Star 1500x Bigger Than Our Sun That Dimmed Unexpectedly'. "
            "Examples of the WRONG style: 'The Universe is Big', 'Facts About Black Holes'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "DEEP SPACE VISUAL RULES:\n"
            "- Scene 1 HOOK: must be visually overwhelming — 'galaxy spiral stars', 'black hole space art', "
            "'asteroid space collision', 'sun solar flare close'.\n"
            "- For black hole topics: 'black hole space visualization', 'space vortex dark'.\n"
            "- For alien planets: 'planet surface barren', 'red planet landscape', 'alien landscape rocks'.\n"
            "- For star topics: 'stars night sky timelapse', 'star cluster nebula', 'supernova explosion'.\n"
            "- For cosmic events: 'meteor shower night', 'asteroid space rocks', 'comet space'.\n"
            "- For scale topics: 'Earth from space', 'milky way night sky', 'moon surface close'.\n"
            "- Pexels has excellent space footage — use specific terms like 'nebula', 'galaxy', 'cosmos', 'space station'."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "The Void With 330M Light-Years of Nothing 🕳️🌌",
    "description": "The Boötes Void is an enormous empty region of space 330 million light-years across. No galaxies. No stars. Just absolute nothing.",
    "hashtags": "#Shorts #Space #Universe #DeepSpace #MindBlown"
  },
  "scenes": [
    {
      "id": 1,
      "text": "330 million light-years of absolute emptiness. No stars. No galaxies. Nothing.",
      "visual_1": "galaxy deep space stars",
      "visual_2": "dark void space black",
      "mood": "eerie"
    }
  ]
}""",
    },
    "4": {
        "name": "👻 Unexplained Mysteries",
        "description": "Fenomena & misteri tak terjawab",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 genuinely unsettling, real-world unexplained mystery for a viral YouTube Short. "
            "Focus on: real disappearances with no explanation, physical anomalies science cannot explain, "
            "ancient structures built with impossible precision, or documented anomalous radio/light signals. "
            "The topic MUST be based on a REAL documented event or discovery — no fiction. "
            "Examples of the RIGHT style: 'The Wow! Signal: A 72-Second Alien Transmission Never Repeated', "
            "'The Oakville Blobs — Gelatinous Blobs That Rained From The Sky Making People Sick', "
            "'The SS Ourang Medan: A Ship Found With All Crew Dead, Faces Frozen in Horror'. "
            "Examples of the WRONG style: 'Mysterious Things', 'Scary Unsolved Cases'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "UNEXPLAINED MYSTERIES VISUAL RULES (CRITICAL — these topics are hard to illustrate):\n"
            "- Scene 1 HOOK: use dark, eerie, dramatic footage — 'storm dark clouds lightning', "
            "'fog forest dark', 'abandoned ship ocean', 'deep ocean underwater dark'.\n"
            "- For disappearance/ship topics: 'ocean storm waves', 'ship wreck underwater', 'empty ship deck'.\n"
            "- For signal/radio topics: 'radio telescope antenna', 'satellite dish sky', 'space observatory night'.\n"
            "- For ancient structure topics: 'ancient ruins stone', 'pyramid aerial view', 'stone monument circle'.\n"
            "- For sky anomaly topics: 'lightning storm sky', 'colorful sky clouds', 'night sky stars'.\n"
            "- For forest/disappearance: 'dark forest fog', 'misty mountains', 'dense jungle'.\n"
            "- CRITICAL: Never use abstract queries like 'mystery' or 'paranormal' — use CONCRETE visual descriptions."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "A Real Alien Signal in 1977 That Lasted 72 Seconds 👽📡",
    "description": "The Wow! Signal was detected on August 15, 1977 and lasted exactly 72 seconds. It has never been explained or repeated since.",
    "hashtags": "#Shorts #Mystery #Aliens #Unexplained #DidYouKnow"
  },
  "scenes": [
    {
      "id": 1,
      "text": "August 15, 1977: a 72-second signal from deep space. Never repeated. Never explained.",
      "visual_1": "radio telescope antenna night",
      "visual_2": "satellite dish sky stars",
      "mood": "eerie"
    }
  ]
}""",
    },
    "5": {
        "name": "🌊 Ocean Secrets",
        "description": "Misteri dan keajaiban lautan dalam",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 stunning, fear-inducing ocean secret for a viral YouTube Short. "
            "Focus on: creatures found at extreme depths with real measurements, underwater geological events, "
            "lost ships or cities confirmed by sonar, or extreme pressure/darkness facts with real data. "
            "The topic MUST include at least one specific depth (in meters/feet) or size measurement. "
            "Examples of the RIGHT style: 'The Bloop: A Sound 5x Louder Than Any Animal Recorded at 950m Depth', "
            "'The Baltic Sea Anomaly: A 60-Meter Disc Found 90m Underwater', "
            "'The Zone of Death in the Pacific Where No Life Exists for 400km'. "
            "Examples of the WRONG style: 'Deep Ocean Facts', 'Scary Sea Creatures'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "OCEAN SECRETS VISUAL RULES:\n"
            "- Scene 1 HOOK: deep, dark, vast ocean imagery — 'deep ocean underwater dark', "
            "'ocean waves surface aerial', 'underwater blue light rays'.\n"
            "- For deep sea creatures: 'jellyfish underwater dark', 'deep sea fish bioluminescent', "
            "'octopus underwater close'.\n"
            "- For shipwrecks: 'shipwreck underwater coral', 'sunken ship ocean floor', 'submarine underwater'.\n"
            "- For ocean floor/geology: 'underwater volcanic vent', 'coral reef ocean floor', 'sand ocean bottom'.\n"
            "- For surface ocean: 'ocean storm waves', 'whale diving ocean', 'ocean horizon sunset'.\n"
            "- For sound/sonar topics: 'sonar wave visualization', 'submarine sonar screen', 'ocean acoustic wave'.\n"
            "- Pexels has excellent ocean footage — 'underwater', 'ocean', 'coral', 'jellyfish' all return great results."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "The Sound Louder Than Any Animal — From 950m Deep 🌊👾",
    "description": "In 1997 NOAA recorded 'The Bloop' — a sound 5x louder than the blue whale at 950 meters depth. Scientists still argue about what made it.",
    "hashtags": "#Shorts #Ocean #DeepSea #Mystery #DidYouKnow"
  },
  "scenes": [
    {
      "id": 1,
      "text": "In 1997, a sound 5x louder than any animal was recorded 950 meters underwater.",
      "visual_1": "deep ocean underwater dark blue",
      "visual_2": "ocean waves surface aerial",
      "mood": "eerie"
    }
  ]
}""",
    },
    "6": {
        "name": "🏛️ Lost Civilizations",
        "description": "Peradaban kuno yang hilang & tersembunyi",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 stunning lost civilization topic for a viral YouTube Short. "
            "Focus on: specific ancient ruins found in impossible locations, construction techniques "
            "that modern engineers still cannot replicate, confirmed archaeological discoveries that "
            "rewrote history, or ancient cities swallowed by jungle/ocean. "
            "The topic MUST include at least one specific date (year), measurement, or location. "
            "Examples of the RIGHT style: 'Göbekli Tepe Was Built 12,000 Years Ago — 6,000 Before Egypt', "
            "'Sacsayhuamán: 200-Ton Stones Fitted With Zero Gap — No Machine Can Replicate It', "
            "'The Sunken City of Dwarka Found 36 Meters Below The Arabian Sea'. "
            "Examples of the WRONG style: 'Lost Ancient Secrets', 'Ancient Civilizations Were Advanced'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "LOST CIVILIZATIONS VISUAL RULES:\n"
            "- Scene 1 HOOK: ancient + dramatic — 'ancient ruins stone aerial', 'pyramid Egypt aerial', "
            "'stone temple jungle overgrown', 'megalith stone circle sunset'.\n"
            "- For jungle ruins: 'temple jungle overgrown vines', 'Angkor Wat aerial', 'stone ruins forest'.\n"
            "- For desert/sand ruins: 'pyramid desert sand', 'ancient columns desert', 'sphinx Egypt'.\n"
            "- For underwater ruins: 'underwater ruins coral', 'sunken city underwater', 'archaeological dive'.\n"
            "- For construction feats: 'large stone blocks wall', 'ancient stone carving', 'quarry stones massive'.\n"
            "- For astronomical alignment: 'stone circle sunrise', 'ancient observatory', 'sun through stone arch'.\n"
            "- AVOID vague queries like 'ancient civilization' — Pexels needs CONCRETE nouns: 'pyramid', 'ruins', 'temple'."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "Built 12,000 Years Ago — Before Egypt Even Existed 🏛️🤯",
    "description": "Göbekli Tepe in Turkey was built 12,000 years ago — 6,000 years before the pyramids. It rewrote everything we knew about human civilization.",
    "hashtags": "#Shorts #History #AncientHistory #LostCivilization #DidYouKnow"
  },
  "scenes": [
    {
      "id": 1,
      "text": "Turkey, 9600 BC. Humans built a massive stone temple 6,000 years before Egypt.",
      "visual_1": "ancient ruins stone aerial sunset",
      "visual_2": "megalith stone circle desert",
      "mood": "awe"
    }
  ]
}""",
    },
    "7": {
        "name": "🤖 Future Technology",
        "description": "Teknologi masa depan yang akan mengubah dunia",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 jaw-dropping, near-future technology topic for a viral YouTube Short. "
            "Focus on: real technologies already in prototype stage that will disrupt society, "
            "specific inventions with measurable performance breakthroughs, AI capabilities with real benchmarks, "
            "or biotech/neuroscience advances that blur the line between human and machine. "
            "The topic MUST reference real, existing research or a company/lab working on it. "
            "Examples of the RIGHT style: "
            "'Neuralink's Brain Chip Let a Paralyzed Man Control a Computer With His Thoughts', "
            "'This Battery Charges to 80% in 3 Minutes — EV Range Anxiety Is Dead', "
            "'Scientists Grew a Working Mini-Heart From Stem Cells in 14 Days'. "
            "Examples of the WRONG style: 'Future Technology Is Amazing', 'AI Will Change Everything'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "FUTURE TECHNOLOGY VISUAL RULES (CRITICAL — avoid abstract tech terms on Pexels):\n"
            "- Scene 1 HOOK: futuristic + high-impact — 'robot hand close up', 'circuit board close macro', "
            "'server room blue lights', 'data center corridor'.\n"
            "- For AI topics: 'computer screen code', 'laptop screen data', 'programmer coding dark room'.\n"
            "- For brain/neuro tech: 'brain MRI scan', 'human brain anatomy model', 'medical scanner hospital'.\n"
            "- For robotics: 'robot arm factory', 'humanoid robot', 'drone flight aerial'.\n"
            "- For biotech/medical: 'laboratory microscope', 'petri dish lab', 'DNA helix model'.\n"
            "- For energy/battery: 'electric car charging', 'solar panel field', 'battery cell closeup'.\n"
            "- For space tech: 'rocket launch', 'space station interior', 'astronaut spacewalk'.\n"
            "- GOLDEN RULE: Replace abstract tech terms with physical objects Pexels understands: "
            "'quantum' → 'laser laboratory', 'AI' → 'computer screen code', 'nano' → 'microscope macro'."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "A Paralyzed Man Controlled a PC With His Mind 🧠💻",
    "description": "Neuralink implanted a chip in a paralyzed man's brain, letting him move a cursor and type using only his thoughts. This changes everything.",
    "hashtags": "#Shorts #Tech #AI #Neuralink #FutureTech"
  },
  "scenes": [
    {
      "id": 1,
      "text": "A paralyzed man moved a computer cursor using only his brain — no hands.",
      "visual_1": "brain MRI scan hospital",
      "visual_2": "computer screen code data",
      "mood": "awe"
    }
  ]
}""",
    },
    "8": {
        "name": "🐉 Extreme Nature",
        "description": "Fenomena dan keajaiban alam ekstrem",
        "mode": "edutainment",
        "topic_prompt": (
            "Give me 1 breathtaking, extreme nature topic for a viral YouTube Short. "
            "Focus on: natural phenomena with exact measurable scale (size, speed, temperature, force), "
            "survival adaptations that seem scientifically impossible, extreme weather events with real records, "
            "or geological events that reshaped continents. "
            "The topic MUST include at least one specific measurement (km/h, °C, km, tons, years). "
            "Examples of the RIGHT style: "
            "'The 1960 Chile Earthquake Was So Powerful It Made The Earth Ring Like a Bell for 2 Days', "
            "'The Tardigrade Can Survive -272°C, Radiation, and the Vacuum of Space', "
            "'The Rogue Wave Measured at 29 Meters That Appeared Out of Nowhere in the North Sea'. "
            "Examples of the WRONG style: 'Nature is Extreme', 'Scary Animals Facts'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "EXTREME NATURE VISUAL RULES (strongest category for Pexels footage):\n"
            "- Scene 1 HOOK: maximum visual impact — 'volcanic eruption lava close', 'tornado storm road', "
            "'lightning strike storm dark', 'massive wave ocean surfer'.\n"
            "- For earthquakes/geological: 'earthquake cracked ground', 'landslide mountain', 'geyser eruption'.\n"
            "- For volcanoes: 'volcano eruption lava', 'lava flow ocean', 'volcanic ash cloud'.\n"
            "- For storms: 'hurricane storm aerial', 'tornado funnel field', 'storm lightning sea'.\n"
            "- For wildlife survival: 'lion hunting prey', 'eagle diving catch', 'wolf pack snow'.\n"
            "- For extreme creatures: 'deep forest spider close', 'snake striking close', 'scorpion desert'.\n"
            "- For water: 'waterfall powerful', 'tsunami wave shore', 'flood city water'.\n"
            "- This category is the easiest — Pexels has abundant footage. Be specific with animal/event names."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "This Tiny Animal Survives -272°C and Outer Space 🐛🌌",
    "description": "The Tardigrade is 0.5mm long but can survive temperatures near absolute zero, radiation, and the vacuum of space for 10 days.",
    "hashtags": "#Shorts #Nature #Science #Animals #MindBlown"
  },
  "scenes": [
    {
      "id": 1,
      "text": "This 0.5mm creature survived -272 Celsius, radiation, and the vacuum of space.",
      "visual_1": "microscope macro insect close",
      "visual_2": "frozen ice crystal close macro",
      "mood": "shocking"
    }
  ]
}""",
    },
    "9": {
        "name": "🗺️ Travel Scenery (BGM Only)",
        "description": "Pemandangan indah dari berbagai penjuru dunia — hanya musik, tanpa narasi",
        "mode": "scenery",
        "topic_prompt": (
            "Give me 1 visually stunning travel destination for a cinematic scenery YouTube Short. "
            "Choose a world-famous OR hidden gem location known for breathtaking visual variety. "
            "The destination should offer a mix of: iconic architecture OR dramatic landscapes, "
            "golden-hour lighting opportunities, aerial and street-level contrast, and vibrant color. "
            "Examples of great choices: 'Paris at Golden Hour', 'Bali Rice Terraces at Sunrise', "
            "'Tokyo Neon Nights', 'Santorini Cliffside Sunset', 'Patagonia Glaciers and Peaks', "
            "'Kyoto Cherry Blossom Season', 'Dubai Skyline Night', 'Cappadocia Hot Air Balloons'. "
            "Return ONLY the destination + optional mood descriptor (e.g. 'Kyoto at Cherry Blossom'). "
            "No quotes, no commentary."
        ),
        "visual_guide": (
            "TRAVEL SCENERY VISUAL RULES (BGM-only — no narration, purely cinematic):\n"
            "- Scene 1 OPENING: iconic establishing shot — 'Eiffel Tower aerial golden hour', "
            "'Bali rice terrace sunrise aerial', 'Tokyo skyscraper night neon'.\n"
            "- Mix these 4 shot types across 8 scenes for cinematic variety:\n"
            "  1. AERIAL: wide overhead drone view — 'city aerial skyline', 'island aerial ocean'.\n"
            "  2. LANDMARK: iconic close or medium — 'Colosseum Rome exterior', 'Big Ben London'.\n"
            "  3. STREET/LIFE: people + culture — 'street market Asia', 'cafe Paris sidewalk'.\n"
            "  4. NATURE DETAIL: texture + light — 'cherry blossom petals', 'ocean waves shore sunset'.\n"
            "- Include time-of-day variety: dawn, golden hour, blue hour, night.\n"
            "- Pexels query tips for travel: '[landmark name]', '[city] aerial', '[city] street', "
            "'[city] night', '[nature element] [country]'.\n"
            "- ALWAYS use 1-4 specific words. Never just 'travel' or 'beautiful' alone."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "Paris Will Always Be Breathtaking 🗼✨",
    "description": "Lose yourself in the timeless beauty of Paris — from the golden glow of the Eiffel Tower to the charming cobblestone streets of Montmartre.",
    "hashtags": "#Shorts #Paris #Travel #Wanderlust #Beautiful"
  },
  "scenes": [
    {
      "id": 1,
      "text": "",
      "visual_1": "Eiffel Tower golden hour aerial",
      "visual_2": "Paris rooftop sunset cityscape",
      "mood": "majestic"
    },
    {
      "id": 2,
      "text": "",
      "visual_1": "Paris cobblestone street cafe",
      "visual_2": "Seine river Paris bridge",
      "mood": "dreamy"
    }
  ]
}""",
    },
}


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Create a .env file or set the environment variable before running."
        )
    return genai.Client(api_key=api_key)


class ContentBrain:
    def get_trending_topic(self, category_key: str = "1", custom_location: str = None):
        """Generate a topic based on the selected category.

        Args:
            category_key: Key from TOPIC_CATEGORIES dict (e.g. "1", "9").
            custom_location: For scenery mode (category "9"), an optional specific
                             location override (e.g. "Paris", "Bali", "Jakarta").
        """
        category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
        mode = category["mode"]

        if mode == "scenery" and custom_location:
            topic = f"{custom_location.strip()}"
            print(f"Selected Topic: {topic}")
            return topic

        prompt = category["topic_prompt"]
        client = _get_client()
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
        )
        topic = response.text.strip().strip('"').strip("'")
        print(f"Selected Topic: {topic}")
        return topic

    def generate_script(self, topic: str, category_key: str = "1"):
        """Generate a full script + SEO metadata for the given topic.

        For 'scenery' mode (category_key == "9"), each scene has NO narration text;
        instead it carries rich Pexels visual queries for stunning footage selection.
        """
        print(f"Writing script for: {topic}...")
        category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
        mode = category["mode"]

        if mode == "scenery":
            return self._generate_scenery_script(topic, category)
        else:
            return self._generate_edutainment_script(topic, category)

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_edutainment_script(self, topic: str, category: dict):
        visual_guide = category.get("visual_guide", "")
        few_shot = category.get("few_shot_example", "")

        prompt = f"""
You are the lead scriptwriter and YouTube SEO expert for a viral Edutainment channel.
Topic: {topic}

Generate SEO metadata and 7-8 fast-paced scenes following this proven retention structure:
- Scene 1: High-impact Hook (stops the scroll in the first 3 seconds)
- Scene 2-4: Core Context & Mind-blowing mechanism
- Scene 5-6: Unexpected Twist or Revelation
- Final Scene: Strong Outro / Punchline that sticks

══════════════════════════════════════
UNIVERSAL SCRIPT RULES (ALL CATEGORIES):
══════════════════════════════════════
TEXT RULES:
- "text": Maximum 12-15 words per scene. Punchy, fast-paced narration.
- ANTI-CLICHÉ HOOK: DO NOT start Scene 1 with "What if I told you", "Did you know", or "Have you ever wondered".
  Start Scene 1 IMMEDIATELY with a striking fact, year, measurement, or event name.
- CONCRETE DATA: Include 2-3 real, specific numbers across the script (years, distances, temperatures, sizes).
- FACTUAL INTEGRITY: Do NOT invent fake facts. Let real data drive the impact — no hyperbole.
- JSON SAFETY: Do NOT use double quotes (") inside text fields. Use single quotes (') if needed.

VISUAL RULES:
- "visual_1" & "visual_2": 2 DISTINCT Pexels stock video search queries per scene.
- Use ONLY 1-4 simple, literal, concrete English words per query.
- NEVER use abstract, metaphorical, or poetic terms (e.g., avoid "mystery", "paranormal", "quantum").
  Instead describe the PHYSICAL OBJECT or SCENE you want to see (e.g., "radio telescope night", "lab microscope close").
- Scene 1 visual_1 MUST be a high-action or visually shocking image to stop thumb-scrolling.

METADATA RULES:
- "title": High-CTR viral title with 1-2 emojis, under 60 characters.
- "description": 2-3 engaging sentences. Include the most shocking fact.
- "hashtags": Exactly 5 viral hashtags relevant to this category.

══════════════════════════════════════
CATEGORY-SPECIFIC VISUAL GUIDE:
══════════════════════════════════════
{visual_guide}

══════════════════════════════════════
FEW-SHOT EXAMPLE (match this schema exactly):
══════════════════════════════════════
{few_shot}

Now generate the FULL script for the topic "{topic}" following all rules above.
Return ONLY a strict JSON object. No markdown, no commentary outside JSON.
"""
        return self._call_gemini(prompt)

    def _generate_scenery_script(self, topic: str, category: dict):
        """Generate a BGM-only scenery script — no narration text, rich visuals only."""
        visual_guide = category.get("visual_guide", "")
        few_shot = category.get("few_shot_example", "")

        prompt = f"""
You are a world-class travel cinematographer and YouTube SEO expert.
You are creating a stunning CINEMATIC SCENERY YouTube Short — BGM only, no voice narration.
Destination / Topic: {topic}

Generate SEO metadata and exactly 8 cinematic scenes.

══════════════════════════════════════
STRICT BGM-ONLY SCENERY RULES:
══════════════════════════════════════
1. "text": MUST be an empty string "" for EVERY scene. Absolutely no narration or captions.

2. "visual_1" & "visual_2": 2 DISTINCT, highly specific Pexels stock video search queries.
   - Use 1-4 literal, concrete English words only.
   - Describe the PHYSICAL SCENE: landmark name, lighting condition, shot type.
   - Include EXACTLY the destination name where relevant (e.g., "Eiffel Tower", "Bali rice terrace").
   - Mix shot types for cinematic flow: aerial wide → landmark close → street life → nature detail.
   - Include time-of-day variety across 8 scenes: sunrise, golden hour, blue hour, night.
   - NEVER use vague single words like "travel", "beautiful", "scenery" alone.

3. "mood": One of: cinematic, peaceful, majestic, golden, dreamy, vibrant, serene, breathtaking.

4. "metadata":
   - "title": Aesthetic, wanderlust title with 1-2 emojis, under 60 chars.
   - "description": 2-3 travel-inspiring sentences. Paint a picture of the destination.
   - "hashtags": Exactly 5 viral travel hashtags including the destination name.

══════════════════════════════════════
CATEGORY-SPECIFIC VISUAL GUIDE:
══════════════════════════════════════
{visual_guide}

══════════════════════════════════════
FEW-SHOT EXAMPLE (match this schema exactly):
══════════════════════════════════════
{few_shot}

Now generate the FULL 8-scene script for "{topic}".
Return ONLY a strict JSON object. No markdown, no commentary outside JSON.
"""
        return self._call_gemini(prompt)

    def _call_gemini(self, prompt: str):
        client = _get_client()
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.75,
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
