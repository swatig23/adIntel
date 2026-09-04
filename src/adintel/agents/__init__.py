"""The AdIntel multi-agent pipeline.

Each agent is a focused, single-responsibility module:

* :mod:`ingest`     — pulls competitor ads (Meta Ad Library)
* :mod:`longevity`  — flags "proven winners" (ads running > 90 days)
* :mod:`analyze`    — extracts recurring patterns from winning ads (Gemini vision + long-ctx)
* :mod:`gap`        — compares user's ads vs winning patterns; produces prioritized deltas
* :mod:`create`     — generates fresh ad creatives via Nano Banana + Gemini copy
* :mod:`report`     — synthesizes an executive summary + narrative

They are wired together by :class:`orchestrator.Orchestrator`.
"""
