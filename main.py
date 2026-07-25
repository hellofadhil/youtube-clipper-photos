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
    print("🚀 STARTING AUTOMATION...")

    brain = ContentBrain()
    try:
        topic = brain.get_trending_topic()
        script = brain.generate_script(topic)
    except Exception as error:
        print(f"❌ Brain Error: {error}")
        return

    if not script:
        print("❌ Script generation failed.")
        return

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
        composer.concatenate_with_transitions(final_scene_paths)
        clean_cache()
    else:
        print("❌ Failed to generate any scenes.")


if __name__ == "__main__":
    asyncio.run(main())
