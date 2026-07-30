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


def generate_script_step(category_choice, custom_location="", audio_mode_choice="", video_format_choice="📱 Shorts Mode (9:16 Vertical - ~40s)"):
    """Step 1: Generate AI topic, script, and SEO metadata."""
    clean_cache()
    category_key = parse_category_key(category_choice)
    selected_category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
    is_bgm_only = "BGM Only" in audio_mode_choice
    is_longform = any(k in str(video_format_choice) for k in ["Documentary", "16:9", "Long-Form", "8.5 Min"])

    custom_loc = custom_location.strip() if custom_location and custom_location.strip() else None

    try:
        topic = brain_instance.get_trending_topic(
            category_key=category_key,
            custom_location=custom_loc,
        )

        force_mode = "scenery" if is_bgm_only else "edutainment"
        bgm_mood = brain_instance.get_bgm_mood(topic)

        if is_longform:
            script = brain_instance.generate_longform_script(topic, category_key=category_key)
        else:
            landmarks = brain_instance.get_topic_anchors(topic) if is_bgm_only else []
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

        format_label = "🎬 Long-Form 16:9 Documentary (8.5 Min)" if is_longform else "📱 Shorts 9:16 (~40s)"
        status_msg = (
            f"✅ **Topic Generated Successfully!**\n\n"
            f"📌 **Topic**: {topic}\n"
            f"📐 **Format**: {format_label}\n"
            f"🎭 **Category**: {selected_category['name']}\n"
            f"🎶 **BGM Mood**: {bgm_mood.upper() if bgm_mood else 'N/A'}\n"
            f"🎙️ **Voice Profile**: {selected_category.get('voice', 'en-US-AvaNeural')}\n\n"
            f"💡 *Jika kamu suka topik ini, klik tombol **'🎬 Suka Topik Ini? Langsung Render Video!'** di bawah! "
            f"Atau klik **'🔄 Generate Topik Baru'** jika ingin mencoba topik lain.*"
        )

        return (
            status_msg,
            topic,
            title,
            description,
            hashtags,
            scenes_json_str,
            table_data,
        )
    except Exception as err:
        return f"❌ Error: {str(err)}", "", "", "", "", "[]", None


def fetch_assets_step(scenes_json_str, table_data, video_format_choice="📱 Shorts Mode (9:16 Vertical - ~40s)"):
    """Step 2: Search & download stock video footage for each scene."""
    try:
        scenes = []
        if table_data is not None:
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

        orientation = "landscape" if "Documentary Mode" in video_format_choice else "portrait"
        asset_mgr = AssetManager()
        video_pairs = asset_mgr.get_videos(scenes, orientation=orientation)

        status_lines = [f"✅ **Footage Download Complete ({orientation})!**\n"]
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
    video_format_choice="📱 Shorts Mode (9:16 Vertical - ~40s)",
    progress=gr.Progress(track_tqdm=True),
):
    """Step 3: Render voice narration, ASS subtitles, and final FFmpeg video stitch."""
    try:
        progress(0.1, desc="Parsing scene plan...")
        category_key = parse_category_key(category_choice)
        selected_category = TOPIC_CATEGORIES.get(category_key, TOPIC_CATEGORIES["1"])
        is_bgm_only = "BGM Only" in audio_mode_choice
        is_longform = "Documentary Mode" in video_format_choice
        aspect_ratio = "16:9" if is_longform else "9:16"
        orientation = "landscape" if is_longform else "portrait"

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
            fallback_file = Path.cwd() / "assets" / "final" / "generated_script.json"
            if fallback_file.is_file():
                try:
                    data = json.loads(fallback_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and "scenes" in data and len(data["scenes"]) > 0:
                        scenes = data["scenes"]
                        print(f"📖 Loaded {len(scenes)} scenes automatically from saved generated_script.json")
                        if not topic:
                            topic = data.get("topic", "")
                        if not title and "metadata" in data:
                            title = data["metadata"].get("title", "")
                except Exception as fb_err:
                    print(f"⚠️ Fallback script load error: {fb_err}")

        if not scenes:
            return "❌ No scenes found for rendering. Silakan klik tombol 'Generate Topic & Script' terlebih dahulu di Tab 1.", None, "", gr.update(visible=False), gr.update(visible=False)

        bgm_mood = brain_instance.get_bgm_mood(topic)

        # 1. Process Audio & Narration
        progress(0.3, desc="Generating AI Voice Narration & ASS Subtitles...")
        category_voice = os.getenv("TTS_VOICE") or selected_category.get("voice", "en-US-AvaNeural")
        category_rate = os.getenv("TTS_RATE") or selected_category.get("rate", "+0%")
        audio_engine = AudioEngine(voice=category_voice, rate=category_rate)
        scenes = await audio_engine.process_script(
            scenes, bgm_only=is_bgm_only, title=title, category_name=selected_category.get("name", "")
        )

        # 2. Download Assets if missing
        progress(0.5, desc=f"Fetching video clips ({orientation})...")
        asset_mgr = AssetManager()
        video_pairs = asset_mgr.get_videos(scenes, orientation=orientation)

        # 3. Parallel FFmpeg Render
        progress(0.7, desc=f"Rendering scenes in parallel with FFmpeg ({aspect_ratio})...")
        composer = Composer(aspect_ratio=aspect_ratio)
        final_scene_paths = composer.render_all_scenes(scenes, video_pairs)

        if not final_scene_paths:
            return "❌ Failed to render individual scene MP4s.", None, "", gr.update(visible=False), gr.update(visible=False)

        # 4. Stitch with Transitions
        progress(0.9, desc=f"Stitching final {aspect_ratio} video with transitions...")
        output_name = "final_documentary.mp4" if is_longform else "final_short.mp4"
        final_video_path = composer.concatenate_with_transitions(
            final_scene_paths,
            output_filename=output_name,
            bgm_mood=bgm_mood,
        )

        if not final_video_path or not os.path.exists(final_video_path):
            return "❌ Final stitching failed.", None, "", gr.update(visible=False), gr.update(visible=False)

        # 5. Extract High-Impact Cover Thumbnail from Scene 1
        thumb_path = composer.extract_thumbnail(final_video_path)

        # Extract SEO tags from saved generated_script.json if present
        tags = ""
        fallback_file = Path.cwd() / "assets" / "final" / "generated_script.json"
        if fallback_file.is_file():
            try:
                data = json.loads(fallback_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "metadata" in data:
                    tags = data["metadata"].get("tags", "")
            except Exception:
                pass

        # Save metadata text file
        meta_path = os.path.join(os.path.dirname(final_video_path), "final_short_metadata.txt")
        meta_content = (
            f"TOPIC: {topic}\n\n"
            f"CATEGORY: {selected_category['name']}\n\n"
            f"AUDIO MODE: {'BGM Only' if is_bgm_only else 'Voice + BGM'}\n\n"
            f"TITLE: {title}\n\n"
            f"DESCRIPTION:\n{description}\n\n"
            f"HASHTAGS:\n{hashtags}\n\n"
            f"SEO SEARCH TAGS:\n{tags if tags else 'educational shorts, viral history, documented events, strange history, mystery'}\n\n"
            f"🔴 RECOMMENDED PINNED COMMENT (ENGAGEMENT BOOSTER):\n"
            f"Which part of this story shocked you the most? 💀 Drop your thoughts below! 🔔\n"
        )
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(meta_content)

        progress(1.0, desc="Video rendering complete!")

        thumb_msg = f"\n📸 **Thumbnail Extracted**: `{thumb_path}`" if thumb_path else ""
        status_msg = (
            f"🎉 **Video Render Completed Successfully!**\n\n"
            f"🎬 **File**: `{os.path.basename(final_video_path)}`\n"
            f"📄 **Metadata Saved**: `{meta_path}`"
            f"{thumb_msg}"
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
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
    --primary-gradient: linear-gradient(135deg, #8b5cf6 0%, #6366f1 50%, #3b82f6 100%);
    --accent-gradient: linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%);
    --card-bg: rgba(15, 23, 42, 0.75);
    --border-glow: rgba(99, 102, 241, 0.25);
}

body, .gradio-container {
    background-color: #090d16 !important;
    background-image: 
        radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(236, 72, 153, 0.12) 0px, transparent 50%) !important;
    font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif !important;
    color: #f1f5f9 !important;
}

.main-header {
    text-align: center;
    padding: 32px 24px;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-glow);
    border-radius: 20px;
    margin-bottom: 24px;
    box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.main-header h1 {
    font-size: 2.6rem;
    font-weight: 800;
    margin: 0;
    background: linear-gradient(135deg, #c084fc 0%, #818cf8 50%, #38bdf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
}

.main-header p {
    color: #94a3b8;
    font-size: 1.05rem;
    margin-top: 8px;
    font-weight: 500;
}

.badge-container {
    display: flex;
    justify-content: center;
    gap: 10px;
    margin-top: 16px;
    flex-wrap: wrap;
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 16px;
    border-radius: 9999px;
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    backdrop-filter: blur(8px);
    transition: all 0.3s ease;
}

.badge-active {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(52, 211, 153, 0.3);
    box-shadow: 0 0 12px rgba(52, 211, 153, 0.15);
}

.badge-inactive {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
    box-shadow: 0 0 12px rgba(251, 191, 36, 0.15);
}

/* Custom Gradio Elements Polish */
.gr-button-primary, button.primary-btn {
    background: var(--primary-gradient) !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.35) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.gr-button-primary:hover, button.primary-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.5) !important;
}

.gr-button-secondary {
    background: rgba(30, 41, 59, 0.8) !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    color: #e2e8f0 !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}

.gr-button-secondary:hover {
    background: rgba(51, 65, 85, 0.9) !important;
    border-color: rgba(99, 102, 241, 0.4) !important;
}

div.block, .gr-box, .gr-panel {
    background: var(--card-bg) !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    border-radius: 16px !important;
}

/* Tab styling */
.tabs > .tab-nav > button.selected {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(99, 102, 241, 0.2)) !important;
    border-bottom: 3px solid #818cf8 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}

.tabs > .tab-nav > button {
    font-weight: 600 !important;
    border-radius: 10px 10px 0 0 !important;
}
"""

with gr.Blocks(title="AutoShorts AI — Web Studio", css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.HTML(
        f"""
        <div class="main-header">
            <h1>🎬 AutoShorts AI — Web Studio</h1>
            <p>Generate, Edit, and Render High-Quality YouTube Shorts with AI</p>
            <div class="badge-container">
                <span class="status-badge {'badge-active' if PEXELS_ACTIVE else 'badge-inactive'}">
                    ● Pexels: {'Active' if PEXELS_ACTIVE else 'Disabled'}
                </span>
                <span class="status-badge {'badge-active' if PIXABAY_ACTIVE else 'badge-inactive'}">
                    ● Pixabay Fallback: {'Active' if PIXABAY_ACTIVE else 'Disabled'}
                </span>
                <span class="status-badge badge-active">
                    ⚡ Codec: {VCODEC.upper()}
                </span>
            </div>
        </div>
        """
    )

    # State stores
    scenes_json_state = gr.State("[]")

    with gr.Tabs():
        # ── TAB 1: SCRIPT & SCENE EDITOR STUDIO ──────────────────────────────────
        with gr.TabItem("🧠 Studio Creator & Editor"):
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
                        placeholder="e.g. 'Cats & Raw Fish', 'How Black Holes Work', 'Tokyo'",
                        interactive=True,
                    )
                    video_format_radio = gr.Radio(
                        label="📐 Video Format & Duration Mode",
                        choices=[
                            "📱 Shorts Mode (9:16 Vertical - ~40s)",
                            "🎬 Documentary Mode (16:9 Widescreen - 8.5 Min)",
                        ],
                        value="📱 Shorts Mode (9:16 Vertical - ~40s)",
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
                    status_box_1 = gr.Markdown(value="*Pilih kategori atau ketik topik, lalu klik tombol **Generate Topic & Script**...*")

                    topic_output = gr.Textbox(label="📌 Selected Topic", interactive=False)
                    title_input = gr.Textbox(label="🏷️ Viral Title", interactive=True)
                    desc_input = gr.TextArea(label="📝 SEO Description", interactive=True)
                    tags_input = gr.Textbox(label="3️⃣ Hashtags", interactive=True)

                    direct_render_btn = gr.Button("🎬 Render Shorts Video Sekarang!", variant="primary", size="lg")

            gr.Markdown("---")
            gr.Markdown("### 📜 Interactive Scene Plan Editor")
            gr.Markdown("*Kamu bisa mengedit kalimat narasi atau kata kunci pencarian visual di tabel di bawah sebelum di-render!*")

            scenes_dataframe = gr.Dataframe(
                headers=["Scene ID", "Narration Text", "Visual Search Query 1", "Visual Search Query 2", "Mood"],
                datatype=["number", "str", "str", "str", "str"],
                col_count=(5, "fixed"),
                interactive=True,
                wrap=True,
            )

            with gr.Row():
                with gr.Column(scale=1):
                    tab1_status_box = gr.Markdown(value="")
                    tab1_metadata_output = gr.TextArea(label="📄 Saved SEO Metadata", interactive=False, visible=False)
                with gr.Column(scale=1):
                    tab1_video_player = gr.Video(
                        label="🎥 Rendered Shorts Video Preview",
                        interactive=False,
                        autoplay=True,
                        visible=False,
                    )

        # ── TAB 2: RENDER & EXPORT STUDIO ──────────────────────────────────
        with gr.TabItem("🎬 Render & Export Studio"):
            with gr.Row():
                with gr.Column(scale=1):
                    render_btn = gr.Button("🚀 START FINAL RENDERING", variant="primary", size="lg")
                    status_box_3 = gr.Markdown(value="*Siap untuk melakukan proses rendering video final...*")
                    metadata_output = gr.TextArea(label="📄 Final SEO Metadata (Copy to YouTube)", interactive=False)
                with gr.Column(scale=1):
                    final_video_player = gr.Video(
                        label="🎥 Final Rendered Video (9:16 / 16:9)",
                        interactive=False,
                        autoplay=True,
                    )

    # ── Event Callbacks ──────────────────────────────────────────────────────
    gen_script_btn.click(
        fn=generate_script_step,
        inputs=[category_dropdown, custom_topic_input, audio_mode_radio, video_format_radio],
        outputs=[
            status_box_1,
            topic_output,
            title_input,
            desc_input,
            tags_input,
            scenes_json_state,
            scenes_dataframe,
        ],
    )

    regen_script_btn.click(
        fn=generate_script_step,
        inputs=[category_dropdown, custom_topic_input, audio_mode_radio, video_format_radio],
        outputs=[
            status_box_1,
            topic_output,
            title_input,
            desc_input,
            tags_input,
            scenes_json_state,
            scenes_dataframe,
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
            video_format_radio,
        ],
        outputs=[
            status_box_1,
            final_video_player,
            metadata_output,
            tab1_video_player,
            tab1_metadata_output,
        ],
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
            video_format_radio,
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
