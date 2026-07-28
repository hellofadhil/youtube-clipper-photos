#!/usr/bin/env python3
"""Install the GUI metadata bridge into youtube-clipper-photos.

Run from the repository root:
    python install_gui_fix.py
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

MARKER_BEGIN = "# GUI_METADATA_BRIDGE_BEGIN"
MARKER_END = "# GUI_METADATA_BRIDGE_END"

BRIDGE_IMPORT = f"""{MARKER_BEGIN}
from gui_metadata_bridge import install as _install_gui_metadata_bridge
_install_gui_metadata_bridge()
{MARKER_END}

"""


def insertion_offset(source: str) -> int:
    """Return a safe character offset after docstring/future imports."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0

    lines = source.splitlines(keepends=True)
    line_index = 0

    if tree.body:
        first = tree.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            line_index = getattr(first, "end_lineno", first.lineno)

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            line_index = max(
                line_index,
                getattr(node, "end_lineno", node.lineno),
            )

    return sum(len(line) for line in lines[:line_index])


def patch_entrypoint(path: Path) -> bool:
    if not path.exists():
        print(f"⚠️ Dilewati, file tidak ada: {path}")
        return False

    source = path.read_text(encoding="utf-8")

    if MARKER_BEGIN in source:
        print(f"✅ Sudah terpasang: {path}")
        return False

    backup_path = path.with_suffix(path.suffix + ".gui-fix.bak")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)

    offset = insertion_offset(source)
    patched = source[:offset] + ("\n" if offset else "") + BRIDGE_IMPORT + source[offset:]
    path.write_text(patched, encoding="utf-8")

    print(f"✅ Dipatch: {path}")
    print(f"   Backup : {backup_path}")
    return True


def main() -> None:
    repo_dir = Path.cwd()
    bridge_path = repo_dir / "gui_metadata_bridge.py"

    if not bridge_path.exists():
        raise FileNotFoundError(
            "gui_metadata_bridge.py tidak ditemukan di repository root."
        )

    changed = False
    changed |= patch_entrypoint(repo_dir / "web_app.py")
    changed |= patch_entrypoint(repo_dir / "main.py")

    print()
    if changed:
        print("✅ GUI metadata fix selesai dipasang.")
        print("Jalankan: git add web_app.py main.py gui_metadata_bridge.py")
    else:
        print("✅ Tidak ada perubahan tambahan yang diperlukan.")


if __name__ == "__main__":
    main()
