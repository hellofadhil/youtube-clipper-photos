import asyncio
import os
import shutil
import sys

from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.brain import ContentBrain, TOPIC_CATEGORIES
from modules.composer import Composer


def clean_cache():
    """Delete only generated temporary media inside this project's assets folder."""
    print("🧹 Cleaning up temporary files...")
    assets_root = (os.path.join(os.getcwd(), "assets"))
    folders_to_clean = [
        os.path.join(assets_root, "audio_clips"),
        os.path.join(assets_root, "video_clips"),
        os.path.join(assets_root, "temp"),
    ]

    for folder in folders_to_clean:
        if not os.path.isdir(folder):
            continue
        if os.path.commonpath([os.path.abspath(folder), os.path.abspath(assets_root)]) != os.path.abspath(assets_root):
            print(f"SECURITY ALERT: Skipping unsafe path {folder}")
            continue
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except OSError as error:
                print(f"❌ Failed to delete {file_path}: {error}")
    print("✨ Workspace clean!")


def render_colab_player(video_path: str):
    """Render an embedded HTML5 video player in Google Colab output cell."""
    try:
        import base64
        from IPython.display import HTML, display
        if os.path.exists(video_path):
            with open(video_path, "rb") as f:
                video_b64 = base64.b64encode(f.read()).decode("utf-8")
            html_code = f"""
            <div style="text-align: center; margin: 20px 0;">
                <p style="font-weight: bold; font-size: 16px; color: #4CAF50; margin-bottom: 10px;">
                    🎬 NONTON LANGSUNG PREVIEW VIDEO (Hemat Kuota ~1.5 MB)
                </p>
                <video width="320" height="568" controls autoplay muted style="border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                    <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
                    Browser Anda tidak mendukung HTML5 video.
                </video>
            </div>
            """
            display(HTML(html_code))
    except Exception:
        pass


def display_category_menu():
    """Print the interactive topic category menu and return the user's choice."""
    print("\n" + "=" * 65)
    print("🎬  PILIH KATEGORI KONTEN VIDEO")
    print("=" * 65)
    for key, cat in TOPIC_CATEGORIES.items():
        print(f"  [{key}] {cat['name']}")
        print(f"       {cat['description']}")
    print("=" * 65)
    choice = input("➡️  Masukkan nomor kategori (default: 1): ").strip()
    if choice not in TOPIC_CATEGORIES:
        print(f"⚠️  Pilihan tidak dikenal, menggunakan kategori 1 (Dark History).")
        choice = "1"
    selected = TOPIC_CATEGORIES[choice]
    print(f"\n✅ Kategori dipilih: {selected['name']}\n")
    return choice


async def main():
    print("🚀 STARTING AUTOMATION...\n")

    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    brain = ContentBrain()
    script = None
    topic = None
    landmarks: list[str] = []
    bgm_mood: str | None = None

    # ── Category selection ──────────────────────────────────────────────────
    if auto_yes:
        category_key = os.getenv("CONTENT_CATEGORY", "1")
        if category_key not in TOPIC_CATEGORIES:
            category_key = "1"
        custom_location = os.getenv("SCENERY_LOCATION", "").strip() or None
    else:
        category_key = display_category_menu()
        custom_location = None
        if TOPIC_CATEGORIES[category_key]["mode"] == "scenery":
            loc = input(
                "📍 Masukkan nama lokasi/destinasi (kosongkan untuk acak dari AI): "
            ).strip()
            custom_location = loc if loc else None

    selected_category = TOPIC_CATEGORIES[category_key]
    is_bgm_only = selected_category["mode"] == "scenery"

    # ── Interactive Topic & Script Generation Loop ───────────────────────────────────
    while True:
        print("🧠 Creating Prompt & Generating Topic...")
        try:
            topic = brain.get_trending_topic(
                category_key=category_key,
                custom_location=custom_location,
            )

            # For scenery mode: discover iconic landmarks BEFORE script generation
            if is_bgm_only:
                bgm_mood = brain.get_bgm_mood(topic)
                print(f"🎵 BGM Mood matched: '{bgm_mood}'")
                landmarks = brain.get_location_landmarks(topic)

            script = brain.generate_script(
                topic,
                category_key=category_key,
                landmarks=landmarks if is_bgm_only else None,
            )
        except Exception as error:
            print(f"❌ Brain Error: {error}")
            return

        if not script:
            print("❌ Script generation failed.")
            if auto_yes:
                return
            retry = input("\n🔄 Apakah kamu mau coba generate topik baru? (y/n): ").strip().lower()
            if retry in ["y", "yes"]:
                continue
            else:
                print("👋 Program dihentikan.")
                return

        if isinstance(script, dict) and "scenes" in script:
            metadata = script.get("metadata", {})
            scenes = script.get("scenes", [])
        else:
            metadata = {}
            scenes = script if isinstance(script, list) else []

        # ── Display Topic, SEO Metadata & Script Preview ──────────────────
        print("\n" + "=" * 65)
        print(f"📌 TOPIK TERPILIH : {topic}")
        print(f"🎭 MODE           : {selected_category['name']}")
        if is_bgm_only:
            print("🎵 AUDIO MODE    : Background Music Only (No Voice / No Subtitle)")
            if bgm_mood:
                print(f"🎶 BGM GENRE     : {bgm_mood.upper()}")
            if landmarks:
                print(f"📍 LANDMARKS     : {', '.join(landmarks[:5])}{'...' if len(landmarks) > 5 else ''}")
        if metadata:
            print(f"🏷️  JUDUL VIRAL   : {metadata.get('title', '-')}")
            print(f"📝 DESKRIPSI     : {metadata.get('description', '-')}")
            print(f"3️⃣  HASHTAGS      : {metadata.get('hashtags', '-')}")
        print("=" * 65)
        print("📜 SCENE VISUAL PLAN:")
        for scene in scenes:
            scene_id = scene.get("id", "-")
            mood = scene.get("mood", "N/A")
            text = scene.get("text", "")
            v1 = scene.get("visual_1", "-")
            v2 = scene.get("visual_2", "-")
            print(f"  [Scene {scene_id}] (Mood: {mood})")
            if text:
                print(f"   💬 Narasi  : \"{text}\"")
            else:
                print(f"   🎵 Narasi  : (BGM only — tidak ada narasi)")
            print(f"   🎬 Visual 1: {v1}")
            print(f"   🎬 Visual 2: {v2}")
            print("  " + "-" * 55)
        print("=" * 65 + "\n")

        if auto_yes:
            print("⚡ Mode Non-Interaktif (--yes) terdeteksi. Melanjutkan proses pembuatan video...")
            break

        # Interactive Confirmation 1: Want to make this video?
        confirm_video = input("❓ Apakah kamu ingin membuat video ini? (y/n): ").strip().lower()
        if confirm_video in ["y", "yes"]:
            print("\n🎬 Memulai proses pembuatan visual dan render video...")
            break
        else:
            # Interactive Confirmation 2: Want to generate a new topic?
            confirm_new_topic = input("🔄 Apakah kamu mau generate topik baru? (y/n): ").strip().lower()
            if confirm_new_topic in ["y", "yes"]:
                # Allow changing location for scenery mode on regeneration
                if is_bgm_only:
                    loc = input(
                        "📍 Masukkan nama lokasi baru (kosongkan untuk acak dari AI): "
                    ).strip()
                    custom_location = loc if loc else None
                    landmarks = []  # reset so landmarks are re-fetched for new location
                    bgm_mood = None
                print("\n🔄 Generasi ulang topik baru...\n")
                continue
            else:
                print("\n👋 Pembuatan video dibatalkan oleh pengguna. Sampai jumpa!")
                return

    # ── Render Pipeline ──────────────────────────────────────────────────────
    audio_engine = AudioEngine()
    try:
        scenes = await audio_engine.process_script(scenes, bgm_only=is_bgm_only)
    except Exception as error:
        print(f"❌ Audio Error: {error}")
        return

    try:
        assets_map = AssetManager().get_videos(scenes)
    except Exception as error:
        print(f"❌ Asset Error: {error}")
        return

    composer = Composer()
    final_scene_paths = composer.render_all_scenes(scenes, assets_map)
    if final_scene_paths:
        final_video = composer.concatenate_with_transitions(
            final_scene_paths,
            bgm_mood=bgm_mood,
        )
        if final_video:
            clean_cache()
            meta_path = os.path.join(os.path.dirname(final_video), "final_short_metadata.txt")
            with open(meta_path, "w", encoding="utf-8") as f:
                f.write(f"TOPIC: {topic}\n\n")
                f.write(f"CATEGORY: {selected_category['name']}\n\n")
                f.write(f"AUDIO MODE: {'BGM Only' if is_bgm_only else 'Voice + BGM'}\n\n")
                f.write(f"TITLE: {metadata.get('title', topic)}\n\n")
                f.write(f"DESCRIPTION:\n{metadata.get('description', '')}\n\n")
                f.write(f"HASHTAGS:\n{metadata.get('hashtags', '')}\n")
            print(f"\n🎉 VIDEO SELESAI DIBUAT: {final_video}")
            print(f"📄 METADATA SEO TERSIMPAN: {meta_path}")

            # Generate low-bandwidth 1.5MB preview and display embedded HTML5 player in Colab
            preview_video = composer.generate_preview(final_video)
            if preview_video:
                render_colab_player(preview_video)
    else:
        print("❌ Failed to generate any scenes.")


if __name__ == "__main__":
    asyncio.run(main())
