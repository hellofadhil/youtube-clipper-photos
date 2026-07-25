from pathlib import Path


def test_avatar_logic_is_removed():
    source = Path("modules/composer.py").read_text(encoding="utf-8").lower()
    assert "avatar_path" not in source
    assert "is_avatar" not in source


def test_required_normalization_filters_exist():
    source = Path("modules/composer.py").read_text(encoding="utf-8")
    for token in ["setsar", "fps", "format", "settb", "PTS-STARTPTS"]:
        assert token in source
