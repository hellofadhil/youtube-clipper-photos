import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from dotenv import load_dotenv


class AssetManager:
    def __init__(self):
        load_dotenv()
        self.pexels_api_key = os.getenv("PEXELS_API_KEY")
        self.pixabay_api_key = os.getenv("PIXABAY_API_KEY")

        if not self.pexels_api_key and not self.pixabay_api_key:
            raise RuntimeError(
                "Neither PEXELS_API_KEY nor PIXABAY_API_KEY is set. "
                "Set at least one stock provider API key in your .env file."
            )

        self.pexels_url = "https://api.pexels.com/videos/search"
        self.pixabay_url = "https://pixabay.com/api/videos/"
        self.assets_dir = os.path.join(os.getcwd(), "assets", "video_clips")
        os.makedirs(self.assets_dir, exist_ok=True)

    def search_pexels(self, query, duration_min=3, exclude_url=None):
        """Search Pexels API for vertical/portrait videos."""
        if not self.pexels_api_key or not query or not query.strip():
            return None

        print(f"🔎 Searching Pexels for: '{query}'...")
        headers = {"Authorization": self.pexels_api_key}
        params = {
            "query": query,
            "per_page": 15,
            "orientation": "portrait",
            "size": "medium",
            "locale": "en-US",
        }
        try:
            response = requests.get(
                self.pexels_url,
                headers=headers,
                params=params,
                timeout=10,
            )
            if response.status_code != 200:
                print(f"⚠️ Pexels API Status: {response.status_code}")
                return None

            data = response.json()
            videos = data.get("videos", [])
            if not videos:
                return None

            # Filter portrait aspect ratio (height >= width) and valid duration
            portrait_videos = [
                v for v in videos
                if v.get("duration", 0) >= duration_min and (v.get("height", 0) or 0) >= (v.get("width", 0) or 0)
            ]
            candidates = portrait_videos if portrait_videos else [
                v for v in videos if v.get("duration", 0) >= duration_min
            ] or videos

            if exclude_url:
                filtered = [
                    c for c in candidates
                    if not any(vf.get("link") == exclude_url for vf in c.get("video_files", []))
                ]
                if filtered:
                    candidates = filtered

            selected_video = random.choice(candidates[:5])
            video_files = selected_video.get("video_files", [])
            if not video_files:
                return None

            # Select highest resolution stream
            video_files.sort(
                key=lambda item: (item.get("width", 0) or 0) * (item.get("height", 0) or 0),
                reverse=True,
            )
            return video_files[0]["link"]
        except Exception as error:
            print(f"❌ Error searching Pexels for '{query}': {error}")
            return None

    def search_pixabay(self, query, duration_min=3, exclude_url=None):
        """Search Pixabay API for vertical/portrait videos as fallback."""
        if not self.pixabay_api_key or not query or not query.strip():
            return None

        print(f"🔎 Fallback searching Pixabay for: '{query}'...")
        params = {
            "key": self.pixabay_api_key,
            "q": query,
            "video_type": "all",
            "orientation": "vertical",
            "per_page": 15,
        }
        try:
            response = requests.get(
                self.pixabay_url,
                params=params,
                timeout=10,
            )
            if response.status_code != 200:
                print(f"⚠️ Pixabay API Status: {response.status_code}")
                return None

            data = response.json()
            hits = data.get("hits", [])
            if not hits:
                return None

            valid_hits = [h for h in hits if h.get("duration", 0) >= duration_min]
            candidates = valid_hits if valid_hits else hits

            selected = random.choice(candidates[:5])
            video_dict = selected.get("videos", {})

            # Select highest quality stream (large -> medium -> small)
            for size_key in ["large", "medium", "small"]:
                if size_key in video_dict and video_dict[size_key].get("url"):
                    url = video_dict[size_key]["url"]
                    if not exclude_url or url != exclude_url:
                        return url

            return None
        except Exception as error:
            print(f"❌ Error searching Pixabay for '{query}': {error}")
            return None

    def search_video(self, query, duration_min=3, attempt=1, exclude_url=None):
        """Search primary provider (Pexels) and fall back to secondary (Pixabay) with smart queries."""
        if not query or not query.strip():
            return None

        # Step 1: Try Pexels
        url = self.search_pexels(query, duration_min=duration_min, exclude_url=exclude_url)
        if url and url != exclude_url:
            return url

        # Step 2: Try Pixabay fallback
        if self.pixabay_api_key:
            url = self.search_pixabay(query, duration_min=duration_min, exclude_url=exclude_url)
            if url and url != exclude_url:
                return url

        # Step 3: Refined query attempt on both providers
        if attempt == 1:
            cleaned_words = [w for w in query.split() if len(w) > 3]
            if cleaned_words and len(cleaned_words) < len(query.split()):
                cleaned_query = " ".join(cleaned_words)
                print(f"⚠️ Retrying Pexels/Pixabay with refined query: '{cleaned_query}'...")
                return self.search_video(cleaned_query, duration_min=duration_min, attempt=2, exclude_url=exclude_url)

        # Step 4: Broad fallback attempt on both providers
        if attempt <= 2:
            broad_fallbacks = [
                "dark stormy ocean aerial",
                "planet earth space rotation",
                "aerial landscape drone",
                "galaxy stars deep space",
            ]
            fallback_query = random.choice(broad_fallbacks)
            print(f"⚠️ Query '{query}' yielded 0 videos across providers. Trying broad fallback: '{fallback_query}'...")
            return self.search_video(fallback_query, duration_min=duration_min, attempt=3, exclude_url=exclude_url)

        return None

    def download_video(self, url, filename, retries=3):
        if not url:
            return None
        save_path = os.path.join(self.assets_dir, filename)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return save_path

        for attempt in range(1, retries + 1):
            try:
                with requests.get(url, stream=True, timeout=30) as response:
                    response.raise_for_status()
                    with open(save_path, "wb") as output:
                        for chunk in response.iter_content(chunk_size=65536):
                            if chunk:
                                output.write(chunk)
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    return save_path
            except Exception as error:
                if os.path.exists(save_path):
                    try:
                        os.unlink(save_path)
                    except OSError:
                        pass
                if attempt < retries:
                    print(f"⚠️ Chunk download interrupted for {filename} (Attempt {attempt}/{retries}): {error}. Retrying...")
                    time.sleep(1)
                else:
                    print(f"❌ Error downloading {filename}: {error}")
        return None

    def _process_scene_clips(self, scene):
        scene_id = scene["id"]
        query_a = scene.get("visual_1", scene.get("keywords", "abstract"))
        query_b = scene.get("visual_2", query_a)

        url_a = self.search_video(query_a)
        path_a = self.download_video(url_a, f"scene_{scene_id}_a.mp4") if url_a else None

        # Replacement search for Clip A if initial search/download failed
        if not path_a:
            print(f"⚠️ Scene {scene_id} Clip A failed for '{query_a}'. Running secondary replacement search...")
            fallback_queries = ["cinematic dark atmospheric landscape", "planet earth space aerial", "ocean underwater deep blue"]
            alt_url_a = self.search_video(random.choice(fallback_queries), attempt=3)
            if alt_url_a:
                path_a = self.download_video(alt_url_a, f"scene_{scene_id}_a_alt.mp4")

        url_b = self.search_video(query_b, exclude_url=url_a)
        path_b = self.download_video(url_b, f"scene_{scene_id}_b.mp4") if url_b else None

        # Replacement search for Clip B if initial search/download failed (PREVENTS DUPLICATED CLIP A!)
        if not path_b:
            print(f"⚠️ Scene {scene_id} Clip B failed for '{query_b}'. Running secondary replacement search to prevent clip duplication...")
            fallback_queries = ["galaxy deep space stars rotation", "cinematic technology render", "aerial drone mountain landscape"]
            alt_url_b = self.search_video(random.choice(fallback_queries), attempt=3, exclude_url=url_a)
            if alt_url_b:
                path_b = self.download_video(alt_url_b, f"scene_{scene_id}_b_alt.mp4")

        # Absolute emergency fallback if even secondary replacement search fails
        if not path_a and path_b:
            path_a = path_b
            print(f"⚠️ Emergency Failsafe: Scene {scene_id} Clip A unrecoverable. Reusing Clip B.")
        if not path_b and path_a:
            path_b = path_a
            print(f"⚠️ Emergency Failsafe: Scene {scene_id} Clip B unrecoverable. Reusing Clip A.")

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
