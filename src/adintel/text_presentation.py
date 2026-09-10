"""Deterministic text-truncation helpers for the presentation layer.

The report displays LLM-generated prose (executive summary, gap
recommendations, creative copy). Showing all of it up front makes the
dashboard read like a wall of AI output instead of a distilled briefing.

These helpers never call an LLM and never alter stored/generated content --
they only compute a shorter *preview* string for the template to render,
while the full text stays available for an expandable "read more" section
right next to it. Pure functions, easy to unit test, no Jinja coupling.
"""

from __future__ import annotations

import re


def sentence_preview(text: str, max_chars: int = 220) -> str:
    """Longest prefix of complete sentences that fits within ``max_chars``.

    Prefers to end on a sentence boundary (".", "!", "?") rather than
    cutting mid-sentence. Falls back to a word-boundary truncation with an
    ellipsis only when even the first sentence alone exceeds the budget,
    so we still never cut mid-word.
    """
    stripped = (text or "").strip()
    if len(stripped) <= max_chars:
        return stripped

    sentences = re.split(r"(?<=[.!?])\s+", stripped)
    preview = ""
    for sentence in sentences:
        candidate = f"{preview} {sentence}".strip()
        if len(candidate) > max_chars:
            break
        preview = candidate

    if preview:
        return preview

    # Not even the first sentence fits -- truncate at the last whole word.
    truncated = stripped[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:!? ")
    return f"{truncated}\u2026" if truncated else stripped[:max_chars]


def truncate_words(text: str, max_words: int = 55) -> str:
    """Word-count preview for punchier copy (ad body text) where sentence
    boundaries are less useful than a simple cap.
    """
    stripped = (text or "").strip()
    words = stripped.split()
    if len(words) <= max_words:
        return stripped
    return " ".join(words[:max_words]) + "\u2026"
