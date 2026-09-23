"""Machine-local recall YAML has strict validation and safe defaults."""

import pytest

from app.startup.recall_settings import read_recall_settings


def test_defaults_and_overrides(tmp_path):
    path = tmp_path / "recall.yaml"
    assert read_recall_settings(path).max_memories == 12
    path.write_text("recall:\n  max_memories: 8\n  max_input_tokens: 6000\n")
    settings = read_recall_settings(path)
    assert settings.max_memories == 8
    assert settings.max_concepts == 4
    assert settings.max_input_tokens == 6000
    assert "max_memories: 8" in path.read_text()


@pytest.mark.parametrize(
    "document",
    [
        "[",
        "",
        "recall: null",
        "recall: {max_memories: -1}",
        "recall: {max_concepts: true}",
        "recall: {unknown: 1}",
        'recall: {max_input_tokens: "8000"}',
        "other: {}",
    ],
)
def test_invalid_settings_are_explicit(tmp_path, document):
    path = tmp_path / "recall.yaml"
    path.write_text(document)
    with pytest.raises(ValueError, match="Invalid recall settings"):
        read_recall_settings(path)
