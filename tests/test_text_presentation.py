"""Tests for text_presentation -- deterministic truncation helpers used by
the report templates to keep LLM-generated prose concise on first view.
"""

from adintel.text_presentation import sentence_preview, truncate_words


def test_sentence_preview_returns_short_text_unchanged():
    text = "Short sentence."
    assert sentence_preview(text, max_chars=200) == text


def test_sentence_preview_stops_at_sentence_boundary():
    text = "First sentence here. Second sentence follows. Third one too."
    result = sentence_preview(text, max_chars=25)
    assert result == "First sentence here."
    assert result.endswith(".")


def test_sentence_preview_never_cuts_mid_sentence_when_a_full_sentence_fits():
    text = "Competitors are using longer, highly paced narratives. This creates dramatic tension and premium brand authority."
    result = sentence_preview(text, max_chars=70)
    assert result == "Competitors are using longer, highly paced narratives."
    # Never ends mid-word with no punctuation and no ellipsis marker missing
    assert result[-1] in ".!?"


def test_sentence_preview_falls_back_to_word_boundary_for_one_giant_sentence():
    text = "word " * 50  # one sentence, no punctuation, way over budget
    result = sentence_preview(text.strip(), max_chars=30)
    assert len(result) <= 31  # allows the trailing ellipsis char
    assert result.endswith("\u2026")
    assert " " in result  # still cut on a word boundary, not mid-word


def test_sentence_preview_handles_empty_string():
    assert sentence_preview("") == ""


def test_truncate_words_returns_short_text_unchanged():
    text = "Only a few words here."
    assert truncate_words(text, max_words=55) == text


def test_truncate_words_caps_at_word_count_with_ellipsis():
    text = " ".join(f"word{i}" for i in range(100))
    result = truncate_words(text, max_words=10)
    assert result.endswith("\u2026")
    assert len(result.rstrip("\u2026").split()) == 10


def test_truncate_words_handles_empty_string():
    assert truncate_words("") == ""
