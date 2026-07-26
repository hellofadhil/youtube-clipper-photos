import json
import os
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Visual Query Validator — Auto-detect & replace abstract Pexels queries
# ─────────────────────────────────────────────────────────────────────────────

# Words that cause Pexels to return irrelevant or zero results
_ABSTRACT_TERMS = frozenset([
    "concept", "abstract", "visualization", "visualisation", "anomaly",
    "theory", "phenomenon", "unknown", "paranormal", "metaphor", "idea",
    "void", "pressure", "force", "energy", "power", "darkness", "dark",
    "mystery", "mysterious", "invisible", "abyss", "eerie", "scary",
    "creepy", "glowing", "haunted", "supernatural", "cosmic", "infinite",
    "eternal", "beyond", "ancient", "lost", "hidden", "secret",
    "forbidden", "cursed", "epic", "stunning", "beautiful", "amazing",
])

# Minimum number of NON-abstract concrete words required in a query
_MIN_CONCRETE_WORDS = 1

# Per-category fallback pools — used when a query is too abstract
_VISUAL_FALLBACK_POOLS: dict[str, list[str]] = {
    "1": [  # Dark History
        "battlefield soldiers smoke", "nuclear explosion black white",
        "classified documents desk lamp", "old newspaper archive",
        "army march soldiers", "warship ocean", "prison cell corridor",
        "war memorial grave", "military uniform soldier", "ruins abandoned building",
        "protest crowd street", "government building exterior", "barbed wire fence",
    ],
    "2": [  # Mind-Blowing Science
        "cell division microscope closeup", "lightning strike slow motion",
        "lava flow rock close", "brain MRI scan hospital",
        "laser beam laboratory blue", "DNA model laboratory",
        "chemical reaction colored liquid", "neurons brain anatomy model",
        "microscope macro science", "blood cells microscope",
        "scientist laboratory coat", "telescope observatory night",
    ],
    "3": [  # Deep Space
        "galaxy spiral stars", "star cluster nebula purple",
        "moon surface crater", "rocket launch fire",
        "astronaut spacewalk", "Earth from orbit blue",
        "comet tail space", "meteor shower night sky",
        "telescope observatory dome", "space station interior",
        "sun solar flare orange", "planet surface barren",
    ],
    "4": [  # Unexplained Mysteries
        "storm lightning dark sea", "fog forest road",
        "abandoned ship deck rusted", "radio telescope antenna",
        "stone monument circle field", "dense jungle trees",
        "dark corridor empty hallway", "old lighthouse sea",
        "empty desert road", "cave entrance dark",
        "shipwreck underwater coral", "satellite dish sky",
    ],
    "5": [  # Ocean Secrets
        "deep sea fish underwater", "jellyfish underwater dark blue",
        "coral reef ocean colorful", "ocean waves surface aerial",
        "submarine underwater vessel", "scuba diver ocean reef",
        "whale diving ocean", "shark swimming ocean",
        "ocean floor sand", "underwater cave light rays",
        "sea turtle swimming ocean", "bioluminescent water night",
    ],
    "6": [  # Lost Civilizations
        "pyramid Egypt aerial sand", "ancient temple stone ruins",
        "stone carving wall relief", "archaeological excavation site",
        "jungle overgrown temple", "ancient columns marble",
        "stone circle field sunset", "cave painting prehistoric",
        "stone wall ancient construction", "archaeological artifacts clay",
        "ancient city ruins aerial", "sphinx Egypt desert",
    ],
    "7": [  # Future Technology
        "robot arm factory assembly", "computer screen code dark room",
        "brain MRI scan medical", "server room blue lights",
        "electric car charging station", "drone flight aerial city",
        "laboratory microscope scientist", "solar panel field sky",
        "3D printer technology", "humanoid robot machine",
        "data center corridor lights", "laptop screen programmer",
    ],
    "8": [  # Extreme Nature
        "volcanic eruption lava close", "tornado funnel road field",
        "lightning strike storm night", "ocean wave surfer large",
        "earthquake cracked ground", "flood city water street",
        "hurricane aerial storm", "avalanche snow mountain",
        "wildfire forest flames", "lion hunting prey",
        "eagle diving catch fish", "wolf pack snow forest",
    ],
    "9": [  # Travel Scenery
        "city aerial skyline sunset", "mountain landscape snow peak",
        "beach ocean waves shore", "forest trees sunlight rays",
        "waterfall nature green", "cherry blossom tree pink",
        "river reflection sunset", "coastal cliff ocean",
        "rice terrace aerial green", "lake mountain reflection",
        "cobblestone street evening", "flower field aerial",
    ],
}


def _is_abstract_query(query: str) -> bool:
    """Return True if the query is too abstract for Pexels to handle reliably."""
    words = re.findall(r"[a-z]+", query.lower())
    if not words:
        return True
    concrete_words = [w for w in words if w not in _ABSTRACT_TERMS and len(w) > 2]
    return len(concrete_words) < _MIN_CONCRETE_WORDS


def _sanitize_visual_queries(script: dict, category_key: str) -> dict:
    """Post-process all visual_1 / visual_2 fields in script scenes.

    Replaces abstract or Pexels-unfriendly queries with concrete fallbacks
    from the category's fallback pool, cycling through the pool to keep variety.
    Also removes duplicate queries within the same scene and across adjacent scenes.
    """
    if not isinstance(script, dict) or "scenes" not in script:
        return script

    fallback_pool = _VISUAL_FALLBACK_POOLS.get(category_key, _VISUAL_FALLBACK_POOLS["1"])
    fallback_index = 0
    replaced_count = 0
    seen_queries: set[str] = set()

    def next_fallback(exclude: set[str]) -> str:
        nonlocal fallback_index
        for _ in range(len(fallback_pool)):
            candidate = fallback_pool[fallback_index % len(fallback_pool)]
            fallback_index += 1
            if candidate not in exclude:
                return candidate
        # All exhausted — just return the next one
        result = fallback_pool[fallback_index % len(fallback_pool)]
        fallback_index += 1
        return result

    for scene in script["scenes"]:
        scene_used: set[str] = set()
        for key in ("visual_1", "visual_2"):
            original = scene.get(key, "").strip()
            if not original:
                replacement = next_fallback(seen_queries | scene_used)
                scene[key] = replacement
                scene_used.add(replacement)
                seen_queries.add(replacement)
                replaced_count += 1
                print(f"  🔧 Scene {scene.get('id','?')} {key}: (empty) → '{replacement}'")
                continue

            needs_replace = _is_abstract_query(original) or original in seen_queries
            if needs_replace:
                replacement = next_fallback(seen_queries | scene_used)
                scene[key] = replacement
                scene_used.add(replacement)
                seen_queries.add(replacement)
                replaced_count += 1
                reason = "duplicate" if original in seen_queries else "abstract"
                print(f"  🔧 Scene {scene.get('id','?')} {key} [{reason}]: '{original}' → '{replacement}'")
            else:
                scene_used.add(original)
                seen_queries.add(original)

    if replaced_count > 0:
        print(f"  ✅ Visual query sanitizer: {replaced_count} queries replaced.")
    else:
        print(f"  ✅ Visual query sanitizer: all queries look good!")

    return script


# ─────────────────────────────────────────────────────────────────────────────
# Topic categories
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
            "DARK HISTORY — PEXELS VISUAL RULES:\n"
            "BANNED WORDS (never use alone): 'darkness', 'mystery', 'secret', 'hidden', 'unknown', 'evil', 'cursed'.\n"
            "SUBSTITUTION MAP (use the RIGHT column):\n"
            "  'secret documents'       → 'classified documents desk lamp'\n"
            "  'dark history'           → 'battlefield soldiers smoke'\n"
            "  'evil experiments'       → 'laboratory old equipment'\n"
            "  'war mystery'            → 'warship ocean fire'\n"
            "  'government conspiracy'  → 'government building exterior'\n"
            "  'historical event'       → 'old newspaper archive'\n"
            "SCENE 1 HOOK — pick ONE of: 'nuclear explosion black white', "
            "'battlefield explosion smoke', 'warship fire ocean'.\n"
            "VARIETY GUIDE across 7 scenes:\n"
            "  - 2x war/military: 'soldiers trench war', 'tank battlefield', 'army march'\n"
            "  - 2x institutional: 'laboratory old equipment', 'prison cell corridor', 'courtroom interior'\n"
            "  - 2x document/archive: 'classified documents desk', 'old newspaper archive', 'typewriter paper'\n"
            "  - 1x aftermath: 'ruins abandoned building', 'memorial grave', 'barbed wire fence'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
    },
    {
      "id": 2,
      "text": "Project MKUltra ran 150 experiments across 80 institutions for a decade.",
      "visual_1": "laboratory old equipment hospital",
      "visual_2": "army soldiers march uniform",
      "mood": "tense"
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
            "Examples of the RIGHT style: 'Your Body Replaces 98% of Its Atoms Every Year', "
            "'The Double Slit Experiment Proves Reality Only Exists When Observed', "
            "'A Teaspoon of Neutron Star Weighs 10 Million Tons'. "
            "Examples of the WRONG style: 'Interesting Science Facts', 'How Quantum Physics Works'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "MIND-BLOWING SCIENCE — PEXELS VISUAL RULES:\n"
            "BANNED WORDS (never use alone): 'quantum', 'energy', 'force', 'concept', 'abstract', "
            "'phenomenon', 'glowing', 'infinite', 'cosmic'.\n"
            "SUBSTITUTION MAP (use the RIGHT column):\n"
            "  'quantum effect'         → 'laser beam laboratory blue'\n"
            "  'energy field'           → 'lightning strike slow motion'\n"
            "  'atomic structure'       → 'microscope macro science'\n"
            "  'brain activity'         → 'brain MRI scan hospital'\n"
            "  'cellular biology'       → 'cell division microscope closeup'\n"
            "  'scientific concept'     → 'scientist laboratory coat'\n"
            "  'glowing cells'          → 'microscope fluorescent laboratory'\n"
            "  'neural network'         → 'neurons brain anatomy model'\n"
            "SCENE 1 HOOK — pick ONE of: 'lightning strike slow motion', "
            "'lava flow rock close', 'cell division microscope closeup', 'sun solar flare orange'.\n"
            "VARIETY GUIDE across 7 scenes:\n"
            "  - 2x macro/micro: 'cell microscope closeup', 'chemical reaction laboratory', 'DNA model'\n"
            "  - 2x physics/space: 'laser beam laboratory', 'particle accelerator', 'telescope dome'\n"
            "  - 2x biology: 'brain MRI scan', 'blood cells microscope', 'human body anatomy'\n"
            "  - 1x dramatic nature: 'lightning storm sky', 'lava flow close', 'waterfall powerful'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
      "visual_1": "star explosion supernova space",
      "visual_2": "galaxy deep space blue",
      "mood": "shocking"
    },
    {
      "id": 2,
      "text": "Neutron stars are born when a star 8x the sun's mass collapses in seconds.",
      "visual_1": "telescope observatory dome night",
      "visual_2": "laser beam laboratory blue",
      "mood": "dramatic"
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
            "DEEP SPACE — PEXELS VISUAL RULES:\n"
            "BANNED WORDS (never use alone): 'void', 'cosmic', 'infinite', 'dark', 'eternal', 'beyond'.\n"
            "SUBSTITUTION MAP (use the RIGHT column):\n"
            "  'dark void space'        → 'black space stars distant'\n"
            "  'cosmic energy'          → 'sun solar flare orange'\n"
            "  'infinite universe'      → 'galaxy spiral stars wide'\n"
            "  'black hole concept'     → 'galaxy center bright stars'\n"
            "  'space darkness'         → 'night sky stars timelapse'\n"
            "  'alien world'            → 'red planet surface barren'\n"
            "SCENE 1 HOOK — pick ONE of: 'galaxy spiral stars', 'sun solar flare orange', "
            "'asteroid space rocks', 'rocket launch fire night'.\n"
            "VARIETY GUIDE across 7 scenes:\n"
            "  - 2x space objects: 'star cluster nebula', 'galaxy spiral', 'comet tail space'\n"
            "  - 2x Earth/human scale: 'Earth from orbit blue', 'astronaut spacewalk', 'telescope dome'\n"
            "  - 2x dramatic events: 'meteor shower night sky', 'rocket launch fire', 'moon surface crater'\n"
            "  - 1x planet surface: 'red planet surface barren', 'planet atmosphere clouds'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
      "visual_1": "galaxy spiral stars wide",
      "visual_2": "night sky stars timelapse",
      "mood": "eerie"
    },
    {
      "id": 2,
      "text": "The Boötes Void is so large, 2,000 Milky Way galaxies could fit inside.",
      "visual_1": "Earth from orbit blue",
      "visual_2": "telescope observatory dome night",
      "mood": "awe"
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
            "The topic MUST be based on a REAL documented event or discovery. "
            "Examples of the RIGHT style: 'The Wow! Signal: A 72-Second Alien Transmission Never Repeated', "
            "'The Oakville Blobs — Gelatinous Blobs That Rained From The Sky Making People Sick', "
            "'The SS Ourang Medan: A Ship Found With All Crew Dead, Faces Frozen in Horror'. "
            "Examples of the WRONG style: 'Mysterious Things', 'Scary Unsolved Cases'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "UNEXPLAINED MYSTERIES — PEXELS VISUAL RULES (hardest category — follow closely):\n"
            "BANNED WORDS (never use alone): 'mystery', 'mysterious', 'paranormal', 'eerie', 'creepy', "
            "'haunted', 'supernatural', 'anomaly', 'unknown', 'cursed', 'darkness'.\n"
            "SUBSTITUTION MAP (use the RIGHT column):\n"
            "  'mysterious signal'      → 'radio telescope antenna night'\n"
            "  'paranormal activity'    → 'dark corridor empty hallway'\n"
            "  'mysterious ship'        → 'abandoned ship deck rusted'\n"
            "  'eerie forest'           → 'fog forest road trees'\n"
            "  'unknown creature'       → 'ocean waves dark storm'\n"
            "  'dark mystery'           → 'storm lightning sea waves'\n"
            "  'ancient anomaly'        → 'stone monument circle field'\n"
            "  'haunted location'       → 'abandoned building interior'\n"
            "SCENE 1 HOOK — pick ONE of: 'storm lightning dark sea', 'fog forest road', "
            "'abandoned ship deck rusted', 'ocean waves storm aerial'.\n"
            "VARIETY GUIDE across 7 scenes:\n"
            "  - 2x atmospheric: 'fog forest road', 'storm dark clouds sea', 'lightning strike field'\n"
            "  - 2x location-specific: 'radio telescope antenna', 'stone ruins field', 'old lighthouse sea'\n"
            "  - 2x human/artifact: 'abandoned ship deck', 'old map document', 'archaeological site dig'\n"
            "  - 1x ocean/nature: 'ocean horizon dark', 'underwater cave light', 'dense jungle trees'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
      "visual_1": "storm lightning dark sea waves",
      "visual_2": "radio telescope antenna night",
      "mood": "tense"
    },
    {
      "id": 2,
      "text": "Big Ear Observatory in Ohio picked up a signal 30x stronger than background noise.",
      "visual_1": "satellite dish sky blue",
      "visual_2": "computer screen data green",
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
            "OCEAN SECRETS — PEXELS VISUAL RULES:\n"
            "BANNED WORDS (never use alone): 'abyss', 'darkness', 'pressure', 'deep sea pressure', "
            "'underwater concept', 'ocean mystery', 'deep darkness'.\n"
            "SUBSTITUTION MAP (use the RIGHT column):\n"
            "  'ocean abyss'            → 'deep ocean underwater blue rays'\n"
            "  'underwater pressure'    → 'scuba diver deep underwater'\n"
            "  'deep sea darkness'      → 'jellyfish underwater dark blue'\n"
            "  'ocean mystery'          → 'shipwreck underwater coral'\n"
            "  'deep sea creature'      → 'deep sea fish underwater dark'\n"
            "  'underwater anomaly'     → 'submarine underwater vessel'\n"
            "  'scientific cells'       → 'microscope laboratory closeup'\n"
            "  'bioluminescent glow'    → 'jellyfish underwater blue light'\n"
            "SCENE 1 HOOK — pick ONE of: 'deep ocean underwater blue rays', "
            "'ocean waves aerial dark', 'ocean storm waves aerial', 'whale diving ocean deep'.\n"
            "VARIETY GUIDE across 7 scenes:\n"
            "  - 2x deep water: 'jellyfish underwater dark', 'deep sea fish underwater', 'coral reef colorful'\n"
            "  - 2x surface/aerial: 'ocean waves aerial', 'ocean horizon sunset', 'ship ocean waves'\n"
            "  - 2x creatures: 'whale diving ocean', 'shark swimming ocean', 'sea turtle ocean reef'\n"
            "  - 1x science/lab: 'microscope laboratory closeup', 'sonar screen submarine'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
      "visual_1": "ocean waves aerial dark",
      "visual_2": "deep ocean underwater blue rays",
      "mood": "tense"
    },
    {
      "id": 2,
      "text": "NOAA hydrophones detected it across 5,000 kilometers of open Pacific Ocean.",
      "visual_1": "jellyfish underwater dark blue",
      "visual_2": "scuba diver deep underwater",
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
            "LOST CIVILIZATIONS — PEXELS VISUAL RULES:\n"
            "BANNED WORDS (never use alone): 'ancient', 'lost', 'hidden', 'forgotten', 'mysterious', "
            "'civilization', 'unknown culture', 'epic ruins'.\n"
            "SUBSTITUTION MAP (use the RIGHT column):\n"
            "  'ancient civilization'   → 'pyramid Egypt aerial sand'\n"
            "  'lost city'              → 'jungle overgrown stone temple'\n"
            "  'mysterious ruins'       → 'stone columns ancient Greece'\n"
            "  'hidden temple'          → 'Angkor Wat aerial jungle'\n"
            "  'ancient mystery'        → 'stone carving wall relief'\n"
            "  'sunken city'            → 'underwater ruins coral dive'\n"
            "  'impossible engineering' → 'large stone blocks wall construction'\n"
            "SCENE 1 HOOK — pick ONE of: 'pyramid Egypt aerial sand', 'jungle overgrown stone temple', "
            "'stone monument circle sunset', 'ancient ruins stone columns'.\n"
            "VARIETY GUIDE across 7 scenes:\n"
            "  - 2x iconic landmarks: 'pyramid Egypt sand aerial', 'sphinx Egypt desert', 'Angkor Wat aerial'\n"
            "  - 2x construction detail: 'large stone wall blocks', 'stone carving relief', 'quarry stone massive'\n"
            "  - 2x nature/jungle: 'jungle overgrown temple vines', 'dense jungle trees', 'forest ruins stones'\n"
            "  - 1x underwater/special: 'underwater ruins coral', 'cave painting prehistoric', 'stone circle field'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
      "visual_1": "stone monument circle field sunset",
      "visual_2": "ancient ruins stone columns aerial",
      "mood": "awe"
    },
    {
      "id": 2,
      "text": "Each stone pillar weighs 10 to 20 tons, carved without metal tools.",
      "visual_1": "large stone wall blocks construction",
      "visual_2": "stone carving wall relief closeup",
      "mood": "dramatic"
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
            "'Neuralink Brain Chip Let a Paralyzed Man Control a Computer With His Thoughts', "
            "'This Battery Charges to 80% in 3 Minutes — EV Range Anxiety Is Dead', "
            "'Scientists Grew a Working Mini-Heart From Stem Cells in 14 Days'. "
            "Examples of the WRONG style: 'Future Technology Is Amazing', 'AI Will Change Everything'. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "FUTURE TECHNOLOGY — PEXELS VISUAL RULES (most critical category for abstract avoidance):\n"
            "BANNED WORDS (never use alone): 'quantum', 'nano', 'AI', 'digital', 'virtual', 'cyber', "
            "'data', 'tech', 'innovation', 'futuristic', 'concept', 'visualization', 'hologram'.\n"
            "GOLDEN SUBSTITUTION MAP — replace EVERY abstract tech term with a physical object:\n"
            "  'AI / artificial intelligence' → 'computer screen code dark room'\n"
            "  'quantum computing'            → 'server room blue lights corridor'\n"
            "  'nano technology'              → 'microscope macro laboratory'\n"
            "  'brain-computer interface'     → 'brain MRI scan hospital'\n"
            "  'neural network'               → 'neurons brain anatomy model'\n"
            "  'virtual reality'              → 'VR headset person wearing'\n"
            "  'drone technology'             → 'drone flight aerial city'\n"
            "  'robotics'                     → 'robot arm factory assembly'\n"
            "  'biotech / stem cell'          → 'laboratory petri dish scientist'\n"
            "  'space technology'             → 'rocket launch fire night'\n"
            "  'battery / energy storage'     → 'electric car charging station'\n"
            "  'genetic engineering'          → 'DNA helix model laboratory'\n"
            "SCENE 1 HOOK — pick ONE of: 'robot arm factory assembly', 'brain MRI scan hospital', "
            "'server room blue lights', 'rocket launch fire night'.\n"
            "VARIETY GUIDE across 7 scenes — ALWAYS use physical objects:\n"
            "  - 2x machines/robots: 'robot arm factory', 'humanoid robot machine', '3D printer layer'\n"
            "  - 2x medical/bio: 'brain MRI scan', 'laboratory petri dish', 'DNA model laboratory'\n"
            "  - 2x computing/tech: 'computer screen code', 'server room corridor', 'laptop programmer dark'\n"
            "  - 1x energy/transport: 'electric car charging', 'solar panel field', 'drone aerial city'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
      "visual_1": "brain MRI scan hospital closeup",
      "visual_2": "computer screen code dark room",
      "mood": "awe"
    },
    {
      "id": 2,
      "text": "Neuralink placed 1,024 electrodes into his motor cortex in a 2-hour surgery.",
      "visual_1": "surgeon operating room hospital",
      "visual_2": "microscope macro laboratory science",
      "mood": "dramatic"
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
            "EXTREME NATURE — PEXELS VISUAL RULES (best category for Pexels footage availability):\n"
            "BANNED WORDS (never use alone): 'extreme', 'powerful', 'epic', 'amazing', 'incredible', "
            "'phenomenon', 'force of nature', 'nature concept'.\n"
            "SUBSTITUTION MAP (use the RIGHT column):\n"
            "  'extreme weather'        → 'tornado funnel road field'\n"
            "  'powerful nature'        → 'waterfall powerful rocks'\n"
            "  'nature phenomenon'      → 'volcanic eruption lava close'\n"
            "  'extreme creature'       → 'lion hunting prey grass'\n"
            "  'nature force'           → 'ocean wave surfer large'\n"
            "  'incredible animal'      → 'eagle diving catch fish'\n"
            "SCENE 1 HOOK — pick ONE of: 'volcanic eruption lava close', 'tornado funnel road', "
            "'lightning strike storm night', 'ocean wave surfer large'.\n"
            "VARIETY GUIDE across 7 scenes:\n"
            "  - 2x weather/geological: 'tornado road field', 'hurricane aerial storm', 'earthquake crack ground'\n"
            "  - 2x volcanic/fire: 'volcanic eruption lava', 'lava flow rock ocean', 'wildfire forest flames'\n"
            "  - 2x wildlife: 'lion hunting prey', 'eagle diving fish', 'wolf pack snow forest'\n"
            "  - 1x water/ice: 'waterfall powerful rocks', 'avalanche snow mountain', 'tsunami wave shore'\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL scenes MUST be unique."
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
      "visual_1": "microscope macro insect closeup",
      "visual_2": "frozen ice crystal macro close",
      "mood": "shocking"
    },
    {
      "id": 2,
      "text": "Tardigrades survived all 5 of Earth's mass extinction events across 500 million years.",
      "visual_1": "volcanic eruption lava smoke",
      "visual_2": "meteor shower night sky",
      "mood": "dramatic"
    }
  ]
}""",
    },
    "9": {
        "name": "🎨 Custom Topic",
        "description": "Bebas tentukan topik/lokasi apa saja (misal: 'How AI works', 'Become an Astronaut', 'Paris', dll)",
        "mode": "custom",
        "topic_prompt": (
            "Give me 1 highly engaging, viral topic or destination for a YouTube Short. "
            "Return ONLY the topic title. No quotes, no commentary."
        ),
        "visual_guide": (
            "CUSTOM VISUAL SHORT — PEXELS VISUAL RULES (BGM-only, purely cinematic):\n"
            "BANNED WORDS (never use alone): 'beautiful', 'stunning', 'scenery', 'travel', 'amazing', "
            "'breathtaking', 'wanderlust', 'tourism', 'vacation', 'concept', 'abstract'.\n"
            "VISUAL ANCHORS RULE — each scene MUST focus on its assigned visual anchor topic.\n"
            "MANDATORY 4-SHOT-TYPE MIX across 8 scenes (2 each):\n"
            "  1. AERIAL / WIDE: overhead drone or wide panoramic view\n"
            "  2. OBJECT / FEATURE: main subject, machine, landmark, or tool close-up\n"
            "  3. ACTION / PEOPLE: human interaction, movement, laboratory work, street life\n"
            "  4. DETAIL / TEXTURE: lighting contrast, water, fire, screens, close details\n"
            "ANTI-REPEAT RULE: every visual_1 and visual_2 across ALL 8 scenes MUST be unique (16 unique queries total)."
        ),
        "few_shot_example": """{
  "metadata": {
    "title": "Becoming a NASA Astronaut 🚀👨‍🚀",
    "description": "Experience the intense journey of becoming an astronaut — from zero-gravity underwater training to launching into deep space.",
    "hashtags": "#Shorts #Astronaut #Space #NASA #Future"
  },
  "scenes": [
    {
      "id": 1,
      "text": "",
      "visual_1": "rocket launch pad space shuttle night",
      "visual_2": "astronaut spacesuit helmet closeup",
      "mood": "majestic"
    },
    {
      "id": 2,
      "text": "",
      "visual_1": "zero gravity underwater pool training",
      "visual_2": "scuba diver astronaut suit underwater",
      "mood": "dreamy"
    },
    {
      "id": 3,
      "text": "",
      "visual_1": "centrifuge g force simulator lab",
      "visual_2": "astronaut flight simulator cockpit",
      "mood": "vibrant"
    },
    {
      "id": 4,
      "text": "",
      "visual_1": "astronaut spacewalk Earth orbit view",
      "visual_2": "space station cupola window Earth",
      "mood": "peaceful"
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


# ─────────────────────────────────────────────────────────────────────────────
# BGM Mood Auto-Matching — map destination vibes to music genres
# ─────────────────────────────────────────────────────────────────────────────

# Maps destination keywords (lowercase) → BGM subfolder name
_BGM_DESTINATION_MAP: dict[str, str] = {
    # 🎹 Cinematic Orchestral — classic European cities
    "paris": "cinematic", "rome": "cinematic", "london": "cinematic",
    "vienna": "cinematic", "prague": "cinematic", "florence": "cinematic",
    "barcelona": "cinematic", "amsterdam": "cinematic", "venice": "cinematic",
    "budapest": "cinematic", "athens": "cinematic",
    # 🎸 Lo-fi / Chillhop — East Asian cities
    "tokyo": "lofi", "kyoto": "lofi", "osaka": "lofi",
    "seoul": "lofi", "taipei": "lofi", "busan": "lofi",
    # 🌴 Tropical / Bossa Nova — tropical & beach destinations
    "bali": "tropical", "hawaii": "tropical", "phuket": "tropical",
    "maldives": "tropical", "lombok": "tropical", "raja ampat": "tropical",
    "bohol": "tropical", "palawan": "tropical", "cancun": "tropical",
    "koh samui": "tropical", "pattaya": "tropical",
    # 🎵 Electronic / Synthwave — modern megacities & nightscapes
    "dubai": "electronic", "new york": "electronic", "singapore": "electronic",
    "hong kong": "electronic", "shanghai": "electronic", "las vegas": "electronic",
    "miami": "electronic", "sydney": "electronic", "chicago": "electronic",
    # 🎻 Ambient / Atmospheric — dramatic nature & wilderness
    "patagonia": "ambient", "iceland": "ambient", "norway": "ambient",
    "alaska": "ambient", "tibet": "ambient", "himalayas": "ambient",
    "new zealand": "ambient", "fjord": "ambient", "faroe": "ambient",
    # 🎸 Acoustic Guitar — Mediterranean & countryside
    "santorini": "acoustic", "amalfi": "acoustic", "tuscany": "acoustic",
    "mykonos": "acoustic", "capri": "acoustic", "positano": "acoustic",
    "scotland": "acoustic", "ireland": "acoustic", "portugal": "acoustic",
    # 🥁 World / Cultural — Middle East, Africa, South Asia
    "istanbul": "cultural", "marrakech": "cultural", "cairo": "cultural",
    "mumbai": "cultural", "delhi": "cultural", "jaipur": "cultural",
    "petra": "cultural", "jerusalem": "cultural", "casablanca": "cultural",
    # 🌿 Indonesian cities — tropical + cultural fusion
    "jakarta": "tropical", "yogyakarta": "cultural", "bandung": "tropical",
    "surabaya": "tropical", "medan": "tropical", "makassar": "tropical",
    "manado": "tropical", "komodo": "ambient", "flores": "ambient",
    # 🤖 Electronic / Tech & Future custom topics
    "ai": "electronic", "artificial intelligence": "electronic", "robot": "electronic",
    "tech": "electronic", "code": "electronic", "future": "electronic", "cyber": "electronic",
    "computer": "electronic", "software": "electronic", "hacker": "electronic",
    # 🚀 Ambient / Space, Nature & Science custom topics
    "space": "ambient", "astronaut": "ambient", "cosmos": "ambient", "universe": "ambient",
    "moon": "ambient", "mars": "ambient", "star": "ambient", "ocean": "ambient",
    "nature": "ambient", "forest": "ambient", "mountain": "ambient", "volcano": "ambient",
    # ☕ Lo-fi / Study & Chill custom topics
    "study": "lofi", "chill": "lofi", "cafe": "lofi", "cozy": "lofi", "relax": "lofi",
    "work": "lofi", "focus": "lofi", "reading": "lofi", "aesthetic": "lofi",
    # 🎸 Acoustic / Fitness, Sports & Travel
    "fitness": "acoustic", "workout": "acoustic", "car": "electronic", "speed": "electronic",
}

# Fallback mood if destination not in map
_BGM_DEFAULT_MOOD = "cinematic"


def get_bgm_mood(topic: str) -> str:
    """Return the recommended BGM mood/subfolder name for a destination."""
    topic_lower = topic.lower()
    for keyword, mood in _BGM_DESTINATION_MAP.items():
        if keyword in topic_lower:
            return mood
    return _BGM_DEFAULT_MOOD


class ContentBrain:
    def get_bgm_mood(self, topic: str) -> str:
        """Return the recommended BGM mood/subfolder name for a destination."""
        return get_bgm_mood(topic)

    def get_trending_topic(self, category_key: str = "1", custom_location: str = None):
        """Generate a topic based on the selected category, or use custom_location if provided."""
        if custom_location and custom_location.strip():
            topic = custom_location.strip()
            print(f"Selected Topic: {topic}")
            return topic

        category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
        prompt = category["topic_prompt"]
        client = _get_client()
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
        )
        topic = response.text.strip().strip('"').strip("'")
        print(f"Selected Topic: {topic}")
        return topic

    def get_topic_anchors(self, topic: str) -> list[str]:
        """Discover 10 distinct, filmable visual anchors/spots for ANY custom topic or location.

        Returns a list of specific physical items/places/scenes to be used as unique per-scene visual anchors.
        """
        print(f"🎨 Discovering visual scenes for topic: '{topic}'...")
        prompt = (
            f"You are a professional cinematographer creating a visual YouTube Short about '{topic}'.\n"
            f"List exactly 10 distinct, visually stunning, and FILMABLE scenes, objects, or locations for '{topic}'.\n"
            "Rules:\n"
            "- Each must be a SPECIFIC PHYSICAL SCENE, OBJECT, or LOCATION that can be found as stock video on Pexels.\n"
            "- Use concrete English words describing physical objects (e.g. for 'Become an Astronaut': 'space shuttle launch pad', 'zero gravity underwater pool', 'astronaut spacesuit lab', 'mission control screen').\n"
            "- Return ONLY a JSON array of 10 strings. No explanation, no commentary.\n"
            f"Example for Paris: [\"Eiffel Tower\", \"Montmartre\", \"Seine River\", \"Louvre Museum\", \"Champs-Elysées\", \"Notre-Dame Cathedral\", \"Palais Royal Garden\", \"Sacré-Cœur\", \"Marais District\", \"Arc de Triomphe\"]\n"
            f"Example for Become an Astronaut: [\"Rocket launch pad\", \"Zero gravity underwater pool\", \"Spacesuit fitting lab\", \"Mission control screen\", \"Centrifuge training room\", \"Space station cupola window\", \"Astronaut helmet reflection\", \"Lunar rover moon\", \"Astronaut spacewalk Earth\", \"Spacecraft cockpit\"]\n"
            f"Now list 10 for: '{topic}'"
        )
        client = _get_client()
        try:
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.5,
                ),
            )
            anchors = json.loads(response.text.strip())
            if isinstance(anchors, list) and anchors:
                print(f"  ✅ Found {len(anchors)} visual anchors: {', '.join(anchors)}")
                return anchors
        except Exception as error:
            print(f"  ⚠️  Visual anchor discovery failed: {error}. Using generic scenery approach.")
        return []

    # Alias for backward compatibility
    get_location_landmarks = get_topic_anchors

    def generate_script(self, topic: str, category_key: str = "1",
                        landmarks: list[str] | None = None,
                        force_mode: str | None = None, **kwargs):
        """Generate a full script + SEO metadata, then sanitize visual queries."""
        print(f"Writing script for: {topic}...")
        category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
        mode = force_mode or category.get("mode", "edutainment")
        if mode == "custom":
            mode = "edutainment"  # Default for custom category if not specified

        if mode == "scenery":
            script = self._generate_scenery_script(topic, category, landmarks or [])
        else:
            script = self._generate_edutainment_script(topic, category)

        # ── Post-process: replace abstract / duplicate visual queries ──────
        if script:
            print("🔍 Running visual query sanitizer...")
            script = _sanitize_visual_queries(script, category_key)

        return script

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
- Scene 2-4: Core Context & Mind-blowing mechanism with real data
- Scene 5-6: Unexpected Twist or Revelation
- Final Scene: Strong Outro / Punchline that sticks

══════════════════════════════════════════════════
UNIVERSAL SCRIPT RULES
══════════════════════════════════════════════════
TEXT RULES:
- "text": Maximum 12-15 words per scene. Punchy, fast-paced narration.
- ANTI-CLICHÉ HOOK: Scene 1 MUST NOT start with "What if I told you", "Did you know",
  "Have you ever wondered". Start IMMEDIATELY with a year, number, name, or event.
- CONCRETE DATA: Include 2-3 real specific numbers across the script.
- FACTUAL INTEGRITY: Do NOT invent facts. Real data drives impact — no hyperbole needed.
- JSON SAFETY: Do NOT use double quotes (") inside text fields. Use single quotes (').

VISUAL QUERY RULES (CRITICAL — read every word):
- "visual_1" & "visual_2": 2 DISTINCT Pexels stock video search queries.
- Use ONLY 2-4 simple, literal, concrete English NOUNS and ADJECTIVES.
- Every query must describe a PHYSICAL OBJECT or SCENE you can point at in real life.
- BANNED ABSTRACT WORDS — NEVER use these in any query:
  concept, abstract, mysterious, paranormal, eerie, phenomenon, anomaly, theory,
  darkness (alone), void (alone), pressure (alone), force, energy (alone),
  power (alone), unknown, invisible, cosmic, infinite, eternal, glowing (alone),
  haunted, supernatural, cursed, epic, stunning, beautiful, amazing, incredible.
- ANTI-REPEAT: Every visual_1 and visual_2 across ALL scenes must be UNIQUE.
  Do NOT reuse any query string from a previous scene.
- Scene 1 visual_1 MUST be a high-action explosive image (explosion, storm, fire, impact).

METADATA RULES:
- "title": High-CTR viral title with 1-2 emojis, under 60 characters.
- "description": 2-3 engaging sentences. Include the most shocking concrete fact.
- "hashtags": Exactly 5 viral hashtags relevant to this specific category.

══════════════════════════════════════════════════
CATEGORY-SPECIFIC VISUAL GUIDE:
══════════════════════════════════════════════════
{visual_guide}

══════════════════════════════════════════════════
FEW-SHOT EXAMPLE — match this JSON schema exactly:
══════════════════════════════════════════════════
{few_shot}

Now generate the FULL script for topic: "{topic}"
Follow ALL rules above. Return ONLY valid JSON. No markdown. No commentary outside JSON.
"""
        return self._call_gemini(prompt)

    def _generate_scenery_script(self, topic: str, category: dict,
                                  landmarks: list[str]):
        """Generate a BGM-only scenery script anchored to per-scene unique landmarks."""
        visual_guide = category.get("visual_guide", "")
        few_shot = category.get("few_shot_example", "")

        # Build landmark assignment block
        if landmarks:
            # Ensure we have exactly 8 landmark slots (repeat last if < 8)
            while len(landmarks) < 8:
                landmarks.append(landmarks[-1])
            landmark_block = (
                "LANDMARK ASSIGNMENT (CRITICAL — each scene MUST use its assigned landmark):\n"
                + "\n".join(
                    f"  Scene {i + 1}: Focus on '{landmarks[i]}'"
                    for i in range(8)
                )
                + "\n\nEach scene's visual_1 and visual_2 MUST contain the assigned landmark name "
                  "combined with a specific shot type or lighting condition."
            )
        else:
            landmark_block = (
                "No specific landmarks provided — choose 8 distinct iconic spots for this destination "
                "and assign one unique spot per scene."
            )

        prompt = f"""
You are a world-class travel cinematographer and YouTube SEO expert.
Destination: {topic}
Create a CINEMATIC SCENERY YouTube Short — BGM only, no voice narration, exactly 8 scenes.

══════════════════════════════════════════════════
{landmark_block}
══════════════════════════════════════════════════

STRICT BGM-ONLY SCENERY RULES:
1. "text": MUST be an empty string "" for EVERY scene. No exceptions.

2. VISUAL QUERY RULES (CRITICAL):
   - "visual_1" & "visual_2": 2 DISTINCT, Pexels-ready queries per scene.
   - Each query = [LANDMARK NAME] + [SHOT TYPE] + [optional LIGHTING].
   - BANNED WORDS (never alone): 'beautiful', 'stunning', 'scenery', 'travel',
     'amazing', 'wanderlust', 'tourism', 'vacation', 'breathtaking'.
   - ANTI-REPEAT: All 16 queries across 8 scenes MUST be completely unique strings.

3. SHOT TYPE VARIETY (spread across 8 scenes):
   - aerial / drone view
   - landmark exterior / facade
   - street level / pedestrian
   - interior / market / culture
   - water / nature detail
   - night / dusk / golden hour

4. TIME-OF-DAY SPREAD: Include across 8 scenes — 1x sunrise, 2x golden hour, 1x night.

5. "mood": One of: cinematic, peaceful, majestic, golden, dreamy, vibrant, serene.

6. METADATA:
   - "title": Wanderlust title with 1-2 emojis, under 60 chars.
   - "description": 2-3 vivid sentences that paint a picture of the destination.
   - "hashtags": Exactly 5 hashtags including destination name.

══════════════════════════════════════════════════
CATEGORY-SPECIFIC VISUAL GUIDE:
══════════════════════════════════════════════════
{visual_guide}

══════════════════════════════════════════════════
FEW-SHOT EXAMPLE (schema reference only — use your assigned landmarks above):
══════════════════════════════════════════════════
{few_shot}

Generate the FULL 8-scene script for: "{topic}"
Return ONLY valid JSON. No markdown. No commentary outside JSON.
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
