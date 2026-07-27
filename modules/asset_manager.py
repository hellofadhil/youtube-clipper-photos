import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from dotenv import load_dotenv


class AssetManager:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "PEXELS_API_KEY is not set. Create a .env file or set the environment variable before running."
            )
        self.base_url = "https://api.pexels.com/videos/search"
        self.headers = {"Authorization": self.api_key}
        self.assets_dir = os.path.join(os.getcwd(), "assets", "video_clips")
        os.makedirs(self.assets_dir, exist_ok=True)

    def search_video(self, query, duration_min=3, attempt=1):
        """Search Pexels for a top-rated, high-quality portrait video and return a download URL with smart fallbacks."""
        if not query or not query.strip():
            return None

        print(f"🔎 Searching Pexels for: '{query}'...")
        params = {
            "query": query,
            "per_page": 15,
            "orientation": "portrait",
            "size": "medium",
            "locale": "en-US",
        }
        try:
            response = requests.get(
                self.base_url,
                headers=self.headers,
                params=params,
                timeout=10,
            )
            if response.status_code != 200:
                print(f"⚠️ Pexels API Error: {response.status_code}")
                return None

            data = response.json()
            videos = data.get("videos", [])

            if not videos:
                # Smart fallback chain if exact query returns no results
                if attempt == 1:
                    # Clean words to 2-3 key terms
                    cleaned_words = [w for w in query.split() if len(w) > 3]
                    if cleaned_words and len(cleaned_words) < len(query.split()):
                        cleaned_query = " ".join(cleaned_words)
                        print(f"⚠️ Retrying Pexels with refined query: '{cleaned_query}'...")
                        return self.search_video(cleaned_query, duration_min=duration_min, attempt=2)

                if attempt <= 2:
                    # Fallback to broad ocean/nature portrait fallback
                    broad_fallbacks = ["dark stormy ocean aerial", "planet earth space rotation", "aerial landscape drone"]
                    fallback_query = random.choice(broad_fallbacks)
                    print(f"⚠️ Query '{query}' yielded 0 videos. Trying broad fallback: '{fallback_query}'...")
                    return self.search_video(fallback_query, duration_min=duration_min, attempt=3)

                return None

            # 1. Filter videos with valid duration & native portrait aspect ratio (height >= width)
            portrait_videos = [
                v for v in videos
                if v.get("duration", 0) >= duration_min and (v.get("height", 0) or 0) >= (v.get("width", 0) or 0)
            ]
            candidates = portrait_videos if portrait_videos else [
                v for v in videos if v.get("duration", 0) >= duration_min
            ] or videos

            # 2. Pick strictly from top candidates for quality & variety
            top_candidates = candidates[:5]
            selected_video = random.choice(top_candidates)

            video_files = selected_video.get("video_files", [])
            if not video_files:
                return None

            # 3. Select highest resolution file stream (HD/4K)
            video_files.sort(
                key=lambda item: (item.get("width", 0) or 0) * (item.get("height", 0) or 0),
                reverse=True,
            )
            return video_files[0]["link"]
        except Exception as error:
            print(f"❌ Error searching Pexels for '{query}': {error}")
            return None

    def download_video(self, url, filename):
        if not url:
            return None
        save_path = os.path.join(self.assets_dir, filename)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return save_path
        try:
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(save_path, "wb") as output:
                    for chunk in response.iter_content(chunk_size=16384):
                        if chunk:
                            output.write(chunk)
            return save_path
        except Exception as error:
            print(f"❌ Error downloading {filename}: {error}")
            return None

    def _process_scene_clips(self, scene):
        scene_id = scene["id"]
        query_a = scene.get("visual_1", scene.get("keywords", "abstract"))
        query_b = scene.get("visual_2", query_a)

        url_a = self.search_video(query_a)
        path_a = self.download_video(url_a, f"scene_{scene_id}_a.mp4") if url_a else None

        url_b = self.search_video(query_b)
        path_b = self.download_video(url_b, f"scene_{scene_id}_b.mp4") if url_b else None

        if not path_a and path_b:
            path_a = path_b
            print(f"⚠️ Scene {scene_id} Clip A missing. Using Clip B for both.")
        if not path_b and path_a:
            path_b = path_a
            print(f"⚠️ Scene {scene_id} Clip B missing. Using Clip A for both.")

        if path_a and path_b:
            print(f"✅ Scene {scene_id} Ready (A + B).")
            return scene_id, (path_a, path_b)
        else:
            print(f"❌ Scene {scene_id} Completely Failed (No videos found).")
            return scene_id, None

    def get_videos(self, script_data):
        print("🎬 Starting Parallel Double-Feature Video Download...")
        results_map = {}
        max_workers = min(len(script_data), 8)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_scene = {
                executor.submit(self._process_scene_clips, scene): scene
                for scene in script_data
            }
            for future in as_completed(future_to_scene):
                scene_id, pair = future.result()
                results_map[scene_id] = pair

        video_pairs = [results_map.get(scene["id"]) for scene in script_data]
        return video_pairs
