import asyncio
import os
import shutil

from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.brain import ContentBrain
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





async def main():
    print("🚀 STARTING AUTOMATION...\n")

    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    brain = ContentBrain()
    script = None
    topic = None

    # Interactive Topic & Script Generation Loop
    while True:
        print("🧠 Creating Prompt & Generating Topic...")
        try:
            topic = brain.get_trending_topic()
            script = brain.generate_script(topic)
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

        # Display Topic & Script Preview to User
        print("\n" + "=" * 65)
        print(f"📌 TOPIK TERPILIH: {topic}")
        print("=" * 65)
        print("📜 SKRIP & ANATOMI SCENE:")
        for scene in script:
            scene_id = scene.get("id", "-")
            mood = scene.get("mood", "N/A")
            text = scene.get("text", "")
            v1 = scene.get("visual_1", "-")
            v2 = scene.get("visual_2", "-")
            print(f"  [Scene {scene_id}] (Mood: {mood})")
            print(f"   💬 Narasi  : \"{text}\"")
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
            print("\n🎬 Memulai proses pembuatan audio, visual, dan render video...")
            break
        else:
            # Interactive Confirmation 2: Want to generate a new topic?
            confirm_new_topic = input("🔄 Apakah kamu mau generate topik baru? (y/n): ").strip().lower()
            if confirm_new_topic in ["y", "yes"]:
                print("\n🔄 Generasi ulang topik baru...\n")
                continue
            else:
                print("\n👋 Pembuatan video dibatalkan oleh pengguna. Sampai jumpa!")
                return

    # Render Pipeline
    audio_engine = AudioEngine()
    try:
        script = await audio_engine.process_script(script)
    except Exception as error:
        print(f"❌ Audio Error: {error}")
        return

    try:
        assets_map = AssetManager().get_videos(script)
    except Exception as error:
        print(f"❌ Asset Error: {error}")
        return

    composer = Composer()
    final_scene_paths = composer.render_all_scenes(script, assets_map)
    if final_scene_paths:
        final_video = composer.concatenate_with_transitions(final_scene_paths)
        if final_video:
            clean_cache()
            print(f"\n🎉 VIDEO SELESAI DIBUAT: {final_video}")
    else:
        print("❌ Failed to generate any scenes.")


if __name__ == "__main__":
    asyncio.run(main())

