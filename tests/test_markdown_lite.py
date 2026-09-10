"""Tests for markdown_lite -- the minimal bold/numbered-list renderer used
for Gemini's report output. Kept small and focused on exactly what the
ReportAgent prompt asks the model to produce (see agents/report.py).
"""

from adintel.markdown_lite import render_report_markdown


def test_bold_spans_become_strong_tags():
    result = render_report_markdown("**Headline**\nSome plain text.")
    assert "<strong>Headline</strong>" in result
    assert "**" not in result


def test_numbered_list_items_get_styled_marker_without_doubled_gaps():
    result = render_report_markdown("1. Do the thing.\n2. Do another thing.")
    assert "Do the thing." in result
    assert "Do another thing." in result
    assert '<span class="text-[var(--accent)] font-semibold">1.</span>' in result
    assert '<span class="text-[var(--accent)] font-semibold">2.</span>' in result
    # The newline between items must be consumed by the list-item pattern,
    # not left behind to double up with the caller's pre-wrap line break.
    assert "</span>\n<span" not in result


def test_untrusted_input_is_html_escaped():
    # LLM output is untrusted -- a raw <script> tag must never survive.
    result = render_report_markdown("<script>alert(1)</script> **bold**")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert "<strong>bold</strong>" in result


def test_plain_text_passes_through_unchanged():
    result = render_report_markdown("Just a normal sentence with no markdown.")
    assert result == "Just a normal sentence with no markdown."
