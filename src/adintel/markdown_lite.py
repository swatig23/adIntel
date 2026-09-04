"""Minimal markdown-to-HTML for LLM-generated report text.

Gemini's ReportAgent output consistently uses **bold** headers and simple
numbered lists (see agents/report.py's PROMPT). Pulling in a full markdown
library (e.g. python-markdown) for just these two constructs would be
overkill (YAGNI) -- this covers exactly what the prompt asks the model to
produce, nothing more.

Deliberately NOT a general-purpose markdown renderer: no tables, no nested
lists, no links. If the report prompt grows richer formatting needs later,
reach for a real library instead of growing this file into one.
"""

from __future__ import annotations

import html
import re


def render_report_markdown(text: str) -> str:
    """Converts **bold** spans and numbered-list lines to safe HTML.

    Input is escaped first (untrusted LLM output), then a small set of
    markdown-like patterns are converted to tags. Plain paragraphs are
    preserved via CSS `white-space: pre-wrap` on the caller's side, so we
    don't need to wrap every line in <p> here.
    """
    escaped = html.escape(text)
    bolded = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    # Numbered list items ("1. Do the thing") become block-level spans so
    # they always start on their own line. Consume the trailing newline
    # here -- otherwise the caller's `white-space: pre-wrap` renders BOTH
    # this block's implicit line break AND the literal \n, doubling the
    # gap between list items.
    numbered = re.sub(
        r"^(\d+)\.\s+(.+)$\n?",
        r'<span class="block pl-1"><span class="text-[var(--accent)] font-semibold">\1.</span> \2</span>',
        bolded,
        flags=re.MULTILINE,
    )
    return numbered
