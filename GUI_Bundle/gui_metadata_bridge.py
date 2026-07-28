"""Compatibility bridge that persists GUI-generated script metadata.

This module wraps ContentBrain.generate_script() and writes an atomic output
contract to assets/final. It works for both Gradio GUI and CLI entry points.
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any

_INSTALLED = False
_MARKER = "__gui_metadata_bridge_wrapped__"


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _atomic_write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False),
    )


def _category_name(brain_module: Any, category_key: str) -> str:
    categories = getattr(brain_module, "TOPIC_CATEGORIES", {})
    category = categories.get(str(category_key)) if isinstance(categories, dict) else None

    if category is None:
        return "General Shorts"

    if isinstance(category, dict):
        return str(
            category.get("name")
            or category.get("title")
            or category_key
        ).strip()

    return str(
        getattr(category, "name", None)
        or getattr(category, "title", None)
        or category_key
    ).strip()


def _normalize_hashtags(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        tags = [str(item).strip() for item in value if str(item).strip()]
        value = " ".join(tags)

    text = str(value or "").strip()
    tags = re.findall(r"#[A-Za-z0-9_]+", text)

    if not any(tag.lower() == "#shorts" for tag in tags):
        tags.insert(0, "#Shorts")

    return " ".join(dict.fromkeys(tags)) or "#Shorts"


def _persist_generation(
    brain_module: Any,
    topic: str,
    category_key: str,
    script: Any,
) -> None:
    if not isinstance(script, dict):
        return

    final_dir = Path(
        os.getenv(
            "SHORTS_FINAL_DIR",
            str(Path.cwd() / "assets" / "final"),
        )
    )
    final_dir.mkdir(parents=True, exist_ok=True)

    metadata = script.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    clean_topic = str(topic or metadata.get("topic") or "Untitled YouTube Short").strip()
    title = str(metadata.get("title") or clean_topic).strip()
    description = str(metadata.get("description") or "").strip()
    hashtags = _normalize_hashtags(metadata.get("hashtags"))
    category = _category_name(brain_module, category_key)

    metadata_text = (
        f"TOPIC: {clean_topic}\n"
        f"CATEGORY: {category}\n"
        f"TITLE: {title}\n"
        "DESCRIPTION:\n"
        f"{description}\n"
        "HASHTAGS:\n"
        f"{hashtags}\n"
    )

    _atomic_write_json(final_dir / "generated_script.json", script)
    _atomic_write_text(final_dir / "final_short_metadata.txt", metadata_text)
    _atomic_write_json(
        final_dir / "latest_generation.json",
        {
            "status": "script_ready",
            "topic": clean_topic,
            "category": category,
            "categoryKey": str(category_key),
            "title": title,
            "description": description,
            "hashtags": hashtags,
            "metadataPath": str(final_dir / "final_short_metadata.txt"),
            "scriptPath": str(final_dir / "generated_script.json"),
        },
    )

    print(
        "✅ GUI metadata contract saved:",
        final_dir / "final_short_metadata.txt",
    )


def install() -> bool:
    global _INSTALLED

    if _INSTALLED:
        return True

    try:
        from modules import brain as brain_module
    except Exception as error:
        print(f"⚠️ GUI metadata bridge could not import modules.brain: {error}")
        return False

    content_brain = getattr(brain_module, "ContentBrain", None)
    if content_brain is None:
        print("⚠️ GUI metadata bridge: ContentBrain was not found.")
        return False

    original = getattr(content_brain, "generate_script", None)
    if original is None:
        print("⚠️ GUI metadata bridge: generate_script() was not found.")
        return False

    if getattr(original, _MARKER, False):
        _INSTALLED = True
        return True

    @functools.wraps(original)
    def wrapped(self, *args, **kwargs):
        topic = (
            args[0]
            if args
            else kwargs.get("topic", "Untitled YouTube Short")
        )
        category_key = (
            args[1]
            if len(args) > 1
            else kwargs.get("category_key", "1")
        )

        script = original(self, *args, **kwargs)
        _persist_generation(
            brain_module=brain_module,
            topic=str(topic),
            category_key=str(category_key),
            script=script,
        )
        return script

    setattr(wrapped, _MARKER, True)
    content_brain.generate_script = wrapped
    _INSTALLED = True

    print("✅ GUI metadata bridge installed.")
    return True


# Needed because _normalize_hashtags uses regex.
import re
