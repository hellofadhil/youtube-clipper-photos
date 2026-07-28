# GUI_METADATA_BRIDGE_BEGIN
from gui_metadata_bridge import install as _install_gui_metadata_bridge
_install_gui_metadata_bridge()
# GUI_METADATA_BRIDGE_END

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from dotenv import load_dotenv

import gradio as gr

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

# Auto-detect NVIDIA GPU if FFMPEG_VCODEC is not explicitly set
if "FFMPEG_VCODEC" not in os.environ:
    if shutil.which("nvidia-smi") or os.path.exists("/proc/driver/nvidia"):
        os.environ["FFMPEG_VCODEC"] = "h264_nvenc"

from modules.asset_manager import AssetManager
from modules.audio import AudioEngine
from modules.brain import ContentBrain, TOPIC_CATEGORIES
from modules.composer import Composer


# Check system capabilities
PEXELS_ACTIVE = bool(os.getenv("PEXELS_API_KEY"))
PIXABAY_ACTIVE = bool(os.getenv("PIXABAY_API_KEY"))
VCODEC = os.getenv("FFMPEG_VCODEC", "libx264")


def get_category_choices():
    return [f"[{k}] {v['name']} — {v['description']}" for k, v in TOPIC_CATEGORIES.items()]


def parse_category_key(choice_str: str) -> str:
    if choice_str and choice_str.startswith("["):
        return choice_str.split("]")[0].replace("[", "").strip()
    return "1"


def clean_cache():
    """Delete temporary media inside assets folder for fresh generation."""
    assets_root = os.path.join(os.getcwd(), "assets")
    folders_to_clean = [
        os.path.join(assets_root, "audio_clips"),
        os.path.join(assets_root, "video_clips"),
        os.path.join(assets_root, "temp"),
    ]

    for folder in folders_to_clean:
        if not os.path.isdir(folder):
            continue
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception:
                pass


# Global state holders for multi-step UI flow
brain_instance = ContentBrain()


def generate_script_step(category_choice, custom_location, audio_mode_choice):
    """Step 1: Generate trending topic, SEO metadata, and scene plan."""
    clean_cache()
    category_key = parse_category_key(category_choice)
    selected_category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
    is_bgm_only = "BGM Only" in audio_mode_choice

    custom_loc = custom_location.strip() if custom_location and custom_location.strip() else None

    try:
        topic = brain_instance.get_trending_topic(
            category_key=category_key,
            custom_location=custom_loc,
        )

        force_mode = "scenery" if is_bgm_only else "edutainment"
        bgm_mood = brain_instance.get_bgm_mood(topic)

        if is_bgm_only:
            landmarks = brain_instance.get_topic_anchors(topic)
        else:
            landmarks = []

        script = brain_instance.generate_script(
            topic,
            category_key=category_key,
            landmarks=landmarks if is_bgm_only else None,
            force_mode=force_mode,
        )

        if not script:
            return "❌ Failed to generate script from AI Brain.", "", "", "", "", "[]", None

        if isinstance(script, dict) and "scenes" in script:
            metadata = script.get("metadata", {})
            scenes = script.get("scenes", [])
        else:
            metadata = {}
            scenes = script if isinstance(script, list) else []

        title = metadata.get("title", topic)
        description = metadata.get("description", "")
        hashtags = metadata.get("hashtags", "")

        # Format scenes for interactive Dataframe / JSON editing
        table_data = []
        for sc in scenes:
            table_data.append([
                sc.get("id", 1),
                sc.get("text", ""),
                sc.get("visual_1", ""),
                sc.get("visual_2", ""),
                sc.get("mood", "dramatic")
            ])

        scenes_json_str = json.dumps(scenes, indent=2)

        status_msg = (
            f"✅ **Topic Generated Successfully!**\n\n"
            f"📌 **Topic**: {topic}\n"
            f"🎭 **Category**: {selected_category['name']}\n"
            f"🎶 **BGM Mood**: {bgm_mood.upper() if bgm_mood else 'N/A'}\n"
            f"🎙️ **Voice Profile**: {selected_category.get('voice', 'en-US-AvaNeural')}\n\n"
            f"💡 *Jika kamu suka topik ini, klik tombol **'🎬 Suka Topik Ini? Langsung Render Video!'** di bawah! "
            f"Atau klik **'🔄 Generate Topik Baru'** jika ingin mencoba topik lain.*"
        )

        full_json_payload = script if isinstance(script, dict) else {"metadata": metadata, "scenes": scenes}
        full_json_str = json.dumps(full_json_payload, indent=2, ensure_ascii=False)

        return (
            status_msg,
            topic,
            title,
            description,
            hashtags,
            scenes_json_str,
            table_data,
            full_json_str,
        )
    except Exception as err:
        return f"❌ Error: {str(err)}", "", "", "", "", "[]", None, "{}"


def fetch_assets_step(scenes_json_str, table_data, scenes_json_code=""):
    """Step 2: Search & download stock video footage for each scene."""
    try:
        scenes = []
        if scenes_json_code and isinstance(scenes_json_code, str) and scenes_json_code.strip():
            try:
                parsed = json.loads(scenes_json_code.strip())
                if isinstance(parsed, dict) and "scenes" in parsed:
                    scenes = parsed["scenes"]
                elif isinstance(parsed, list):
                    scenes = parsed
            except Exception:
                scenes = []

        if not scenes and table_data is not None:
            if hasattr(table_data, "empty") and hasattr(table_data, "iterrows"):
                if not table_data.empty:
                    for _, row in table_data.iterrows():
                        r = list(row)
                        if len(r) >= 5:
                            scenes.append({
                                "id": int(r[0]),
                                "text": str(r[1]),
                                "visual_1": str(r[2]),
                                "visual_2": str(r[3]),
                                "mood": str(r[4]),
                            })
            elif isinstance(table_data, dict) and "data" in table_data:
                for r in table_data.get("data", []):
                    if len(r) >= 5:
                        scenes.append({
                            "id": int(r[0]),
                            "text": str(r[1]),
                            "visual_1": str(r[2]),
                            "visual_2": str(r[3]),
                            "mood": str(r[4]),
                        })
            elif isinstance(table_data, (list, tuple)) and len(table_data) > 0:
                for r in table_data:
                    if isinstance(r, (list, tuple)) and len(r) >= 5:
                        scenes.append({
                            "id": int(r[0]),
                            "text": str(r[1]),
                            "visual_1": str(r[2]),
                            "visual_2": str(r[3]),
                            "mood": str(r[4]),
                        })

        if not scenes and scenes_json_str:
            try:
                scenes = json.loads(scenes_json_str)
            except Exception:
                scenes = []

        if not scenes:
            return "❌ No scenes available to fetch assets for.", None, ""

        asset_mgr = AssetManager()
        video_pairs = asset_mgr.get_videos(scenes)

        status_lines = ["✅ **Footage Download Complete!**\n"]
        clip_paths = []

        for idx, pair in enumerate(video_pairs):
            scene_id = scenes[idx].get("id", idx + 1)
            if pair and pair[0] and pair[1]:
                status_lines.append(f"  • Scene {scene_id}: Clip A & Clip B ready")
                clip_paths.append(pair[0])
            else:
                status_lines.append(f"  ⚠️ Scene {scene_id}: Missing footage")

        status_msg = "\n".join(status_lines)
        scenes_updated_json = json.dumps(scenes, indent=2)

        return status_msg, scenes_updated_json, clip_paths[0] if clip_paths else None
    except Exception as err:
        return f"❌ Asset Fetch Error: {str(err)}", scenes_json_str, None


async def render_video_step(
    category_choice,
    topic,
    title,
    description,
    hashtags,
    audio_mode_choice,
    scenes_json_str,
    table_data,
    scenes_json_code="",
    progress=gr.Progress(track_tqdm=True),
):
    """Step 3: Render voice narration, ASS subtitles, and final FFmpeg video stitch."""
    try:
        progress(0.1, desc="Parsing scene plan...")
        category_key = parse_category_key(category_choice)
        selected_category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
        is_bgm_only = "BGM Only" in audio_mode_choice

        scenes = []
        if scenes_json_code and isinstance(scenes_json_code, str) and scenes_json_code.strip():
            try:
                parsed = json.loads(scenes_json_code.strip())
                if isinstance(parsed, dict):
                    if "scenes" in parsed:
                        scenes = parsed["scenes"]
                    meta = parsed.get("metadata", {})
                    if meta.get("title") and (not title or title == topic):
                        title = meta["title"]
                    if meta.get("description") and not description:
                        description = meta["description"]
                    if meta.get("hashtags") and not hashtags:
                        hashtags = meta["hashtags"]
                    if meta.get("topic") and (not topic or topic == "Untitled YouTube Short"):
                        topic = meta["topic"]
                elif isinstance(parsed, list):
                    scenes = parsed
            except Exception:
                scenes = []
        if table_data is not None:
            # Handle pandas DataFrame from Gradio Dataframe component
            if hasattr(table_data, "empty") and hasattr(table_data, "iterrows"):
                if not table_data.empty:
                    for _, row in table_data.iterrows():
                        r = list(row)
                        if len(r) >= 5:
                            scenes.append({
                                "id": int(r[0]),
                                "text": str(r[1]),
                                "visual_1": str(r[2]),
                                "visual_2": str(r[3]),
                                "mood": str(r[4]),
                            })
            elif isinstance(table_data, dict) and "data" in table_data:
                for r in table_data.get("data", []):
                    if len(r) >= 5:
                        scenes.append({
                            "id": int(r[0]),
                            "text": str(r[1]),
                            "visual_1": str(r[2]),
                            "visual_2": str(r[3]),
                            "mood": str(r[4]),
                        })
            elif isinstance(table_data, (list, tuple)) and len(table_data) > 0:
                for r in table_data:
                    if isinstance(r, (list, tuple)) and len(r) >= 5:
                        scenes.append({
                            "id": int(r[0]),
                            "text": str(r[1]),
                            "visual_1": str(r[2]),
                            "visual_2": str(r[3]),
                            "mood": str(r[4]),
                        })

        if not scenes and scenes_json_str:
            try:
                scenes = json.loads(scenes_json_str)
            except Exception:
                scenes = []

        if not scenes:
            return "❌ No scenes found for rendering.", None, "", gr.update(visible=False), gr.update(visible=False)

        bgm_mood = brain_instance.get_bgm_mood(topic)

        # 1. Process Audio & Narration
        progress(0.3, desc="Generating AI Voice Narration & ASS Subtitles...")
        category_voice = os.getenv("TTS_VOICE") or selected_category.get("voice", "en-US-AvaNeural")
        category_rate = os.getenv("TTS_RATE") or selected_category.get("rate", "+0%")
        audio_engine = AudioEngine(voice=category_voice, rate=category_rate)
        scenes = await audio_engine.process_script(scenes, bgm_only=is_bgm_only, title=title)

        # 2. Download Assets if missing
        progress(0.5, desc="Fetching video clips...")
        asset_mgr = AssetManager()
        video_pairs = asset_mgr.get_videos(scenes)

        # 3. Parallel FFmpeg Render
        progress(0.7, desc="Rendering scenes in parallel with FFmpeg...")
        composer = Composer()
        final_scene_paths = composer.render_all_scenes(scenes, video_pairs)

        if not final_scene_paths:
            return "❌ Failed to render individual scene MP4s.", None, "", gr.update(visible=False), gr.update(visible=False)

        # 4. Stitch with Transitions
        progress(0.9, desc="Stitching final 9:16 Shorts video with transitions...")
        final_video_path = composer.concatenate_with_transitions(
            final_scene_paths,
            output_filename="final_short.mp4",
            bgm_mood=bgm_mood,
        )

        if not final_video_path or not os.path.exists(final_video_path):
            return "❌ Final stitching failed.", None, "", gr.update(visible=False), gr.update(visible=False)

        # Save metadata text file
        meta_path = os.path.join(os.path.dirname(final_video_path), "final_short_metadata.txt")
        meta_content = (
            f"TOPIC: {topic}\n\n"
            f"CATEGORY: {selected_category['name']}\n\n"
            f"AUDIO MODE: {'BGM Only' if is_bgm_only else 'Voice + BGM'}\n\n"
            f"TITLE: {title}\n\n"
            f"DESCRIPTION:\n{description}\n\n"
            f"HASHTAGS:\n{hashtags}\n"
        )
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(meta_content)

        progress(1.0, desc="Video rendering complete!")

        status_msg = (
            f"🎉 **Video Render Completed Successfully!**\n\n"
            f"🎬 **File**: `{os.path.basename(final_video_path)}`\n"
            f"📄 **Metadata Saved**: `{meta_path}`"
        )

        return (
            status_msg,
            final_video_path,
            meta_content,
            gr.update(visible=True, value=final_video_path),
            gr.update(visible=True, value=meta_content),
        )

    except Exception as err:
        return f"❌ Render Error: {str(err)}", None, "", gr.update(visible=False), gr.update(visible=False)


def sync_render_video_wrapper(*args):
    """Bridge Gradio sync callback to async render function."""
    return asyncio.run(render_video_step(*args))


# ─────────────────────────────────────────────────────────────────────────────
# Gradio Studio UI Layout
# ─────────────────────────────────────────────────────────────────────────────

custom_css = """
body, .gradio-container {
    background-color: #0f172a;
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}
.main-header {
    text-align: center;
    padding: 20px 0 10px 0;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 2px solid #334155;
    margin-bottom: 20px;
    border-radius: 12px;
}
.main-header h1 {
    color: #f8fafc;
    font-size: 2.2rem;
    font-weight: 800;
    margin: 0;
}
.main-header p {
    color: #94a3b8;
    font-size: 1rem;
    margin-top: 5px;
}
.status-badge {
    display: inline-block;
    padding: 4px 12px;
    margin: 0 5px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}
.badge-active { background-color: #064e3b; color: #34d399; }
.badge-inactive { background-color: #451a03; color: #fbbf24; }
"""

with gr.Blocks(title="AutoShorts AI — Web Studio", css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.HTML(
        f"""
        <div class="main-header">
            <h1>🎬 AutoShorts AI — Web Studio</h1>
            <p>Generate, Edit, and Render High-Quality YouTube Shorts with AI</p>
            <div style="margin-top: 10px;">
                <span class="status-badge {'badge-active' if PEXELS_ACTIVE else 'badge-inactive'}">
                    Pexels: {'Active' if PEXELS_ACTIVE else 'Disabled'}
                </span>
                <span class="status-badge {'badge-active' if PIXABAY_ACTIVE else 'badge-inactive'}">
                    Pixabay Fallback: {'Active' if PIXABAY_ACTIVE else 'Disabled'}
                </span>
                <span class="status-badge badge-active">
                    Codec: {VCODEC.upper()}
                </span>
            </div>
        </div>
        """
    )

    # State stores
    scenes_json_state = gr.State("[]")

    with gr.Tabs():
        # ── TAB 1: GENERATE SCRIPT & TOPIC ──────────────────────────────────
        with gr.TabItem("1. 🧠 Topic & Script Generator"):
            with gr.Row():
                with gr.Column(scale=1):
                    category_dropdown = gr.Dropdown(
                        label="📌 Choose Content Category",
                        choices=get_category_choices(),
                        value=get_category_choices()[0],
                        interactive=True,
                    )
                    custom_topic_input = gr.Textbox(
                        label="📍 Custom Topic / Location (Optional)",
                        placeholder="e.g. 'How AI works', 'Become an Astronaut', 'Paris'",
                        interactive=True,
                    )
                    audio_mode_radio = gr.Radio(
                        label="🔊 Audio Mode",
                        choices=[
                            "🎙️ Voice + Subtitles + BGM (Edutainment)",
                            "🎵 BGM Only (Cinematic Scenery)",
                        ],
                        value="🎙️ Voice + Subtitles + BGM (Edutainment)",
                        interactive=True,
                    )
                    with gr.Row():
                        gen_script_btn = gr.Button("🧠 Generate Topic & Script", variant="primary", size="lg")
                        regen_script_btn = gr.Button("🔄 Generate Topik Baru", variant="secondary", size="lg")

                with gr.Column(scale=2):
                    status_box_1 = gr.Markdown(value="*Click button to generate topic & script...*")

                    topic_output = gr.Textbox(label="📌 Selected Topic", interactive=False)
                    title_input = gr.Textbox(label="🏷️ Viral Title", interactive=True)
                    desc_input = gr.TextArea(label="📝 SEO Description", interactive=True)
                    tags_input = gr.Textbox(label="3️⃣ Hashtags", interactive=True)

                    direct_render_btn = gr.Button("🎬 Suka Topik Ini? Langsung Render Video!", variant="stop", size="lg")

            gr.Markdown("### 📜 Interactive Scene Plan Editor")
            gr.Markdown("*You can edit narration text or visual queries directly in the table below before rendering!*")

            scenes_dataframe = gr.Dataframe(
                headers=["Scene ID", "Narration Text", "Visual Search Query 1", "Visual Search Query 2", "Mood"],
                datatype=["number", "str", "str", "str", "str"],
                col_count=(5, "fixed"),
                interactive=True,
                wrap=True,
            )

            with gr.Accordion("📝 Raw JSON Script Editor (Optionally Edit or Paste Custom JSON Here)", open=False):
                gr.Markdown("*Tip: You can edit or paste a full JSON script structure (with metadata and scenes) below. The render engine will automatically prioritize this JSON if filled!*")
                scenes_json_code = gr.Code(
                    label="Raw JSON Script (Editable)",
                    language="json",
                    interactive=True,
                    lines=12,
                )

            gr.Markdown("---")
            with gr.Row():
                with gr.Column(scale=1):
                    tab1_status_box = gr.Markdown(value="")
                    tab1_metadata_output = gr.TextArea(label="📄 Saved SEO Metadata", interactive=False, visible=False)
                with gr.Column(scale=1):
                    tab1_video_player = gr.Video(
                        label="🎥 Rendered Shorts Video (9:16)",
                        interactive=False,
                        autoplay=True,
                        visible=False,
                    )

        # ── TAB 2: FOOTAGE PREVIEW ──────────────────────────────────────────
        with gr.TabItem("2. 🖼️ Visual Footage Preview"):
            with gr.Row():
                with gr.Column(scale=1):
                    fetch_assets_btn = gr.Button("🔎 Fetch & Download Video Clips", variant="secondary", size="lg")
                    status_box_2 = gr.Markdown(value="*Click to search and preview stock footage...*")
                with gr.Column(scale=1):
                    preview_clip = gr.Video(label="🎬 Sample Footage Preview", interactive=False)

        # ── TAB 3: RENDER & EXPORT ──────────────────────────────────────────
        with gr.TabItem("3. 🎬 Render Final Short"):
            with gr.Row():
                with gr.Column(scale=1):
                    render_btn = gr.Button("🎬 RENDER FINAL SHORTS VIDEO", variant="primary", size="lg")
                    status_box_3 = gr.Markdown(value="*Ready to render final video...*")
                    metadata_output = gr.TextArea(label="📄 Final SEO Metadata", interactive=False)
                with gr.Column(scale=1):
                    final_video_player = gr.Video(
                        label="🎥 Final Rendered Shorts (9:16)",
                        interactive=False,
                        autoplay=True,
                    )

    # ── Event Callbacks ──────────────────────────────────────────────────────
    gen_script_btn.click(
        fn=generate_script_step,
        inputs=[category_dropdown, custom_topic_input, audio_mode_radio],
        outputs=[
            status_box_1,
            topic_output,
            title_input,
            desc_input,
            tags_input,
            scenes_json_state,
            scenes_dataframe,
            scenes_json_code,
        ],
    )

    regen_script_btn.click(
        fn=generate_script_step,
        inputs=[category_dropdown, custom_topic_input, audio_mode_radio],
        outputs=[
            status_box_1,
            topic_output,
            title_input,
            desc_input,
            tags_input,
            scenes_json_state,
            scenes_dataframe,
            scenes_json_code,
        ],
    )

    direct_render_btn.click(
        fn=sync_render_video_wrapper,
        inputs=[
            category_dropdown,
            topic_output,
            title_input,
            desc_input,
            tags_input,
            audio_mode_radio,
            scenes_json_state,
            scenes_dataframe,
            scenes_json_code,
        ],
        outputs=[
            status_box_1,
            final_video_player,
            metadata_output,
            tab1_video_player,
            tab1_metadata_output,
        ],
    )

    fetch_assets_btn.click(
        fn=fetch_assets_step,
        inputs=[scenes_json_state, scenes_dataframe, scenes_json_code],
        outputs=[status_box_2, scenes_json_state, preview_clip],
    )

    render_btn.click(
        fn=sync_render_video_wrapper,
        inputs=[
            category_dropdown,
            topic_output,
            title_input,
            desc_input,
            tags_input,
            audio_mode_radio,
            scenes_json_state,
            scenes_dataframe,
            scenes_json_code,
        ],
        outputs=[
            status_box_3,
            final_video_player,
            metadata_output,
            tab1_video_player,
            tab1_metadata_output,
        ],
    )


if __name__ == "__main__":
    is_colab = "google.colab" in sys.modules or os.path.exists("/content")
    print(f"🚀 Launching AutoShorts AI Web Studio (Colab Mode: {is_colab})...")
    demo.queue().launch(
        share=is_colab,
        server_name="0.0.0.0",
        server_port=7860,
        inbrowser=not is_colab,
    )
