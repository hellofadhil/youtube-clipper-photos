import os
import random

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

    def search_video(self, query, duration_min=4):
        """Search Pexels for a portrait video and return a download URL."""
        print(f"🔎 Searching Pexels for: '{query}'...")
        params = {
            "query": query,
            "per_page": 5,
            "orientation": "portrait",
            "size": "medium",
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
            if not data.get("videos"):
                if " " in query:
                    simple_query = query.split()[-1]
                    print(f"⚠️ No results. Retrying with '{simple_query}'...")
                    return self.search_video(simple_query)
                return None

            valid_videos = [
                video for video in data["videos"] if video["duration"] >= duration_min
            ] or data["videos"]
            selected_video = random.choice(valid_videos)
            video_files = selected_video["video_files"]
            video_files.sort(
                key=lambda item: item["width"] * item["height"],
                reverse=True,
            )
            return video_files[0]["link"]
        except Exception as error:
            print(f"❌ Error searching Pexels: {error}")
            return None

    def download_video(self, url, filename):
        save_path = os.path.join(self.assets_dir, filename)
        if os.path.exists(save_path):
            return save_path
        try:
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with open(save_path, "wb") as output:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            output.write(chunk)
            return save_path
        except Exception as error:
            print(f"❌ Error downloading {filename}: {error}")
            return None

    def get_videos(self, script_data):
        print("🎬 Starting Double-Feature Video Download...")
        video_pairs = []
        for scene in script_data:
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
                video_pairs.append((path_a, path_b))
                print(f"✅ Scene {scene_id} Ready (A + B).")
            else:
                video_pairs.append(None)
                print(f"❌ Scene {scene_id} Completely Failed (No videos found).")
        return video_pairs
