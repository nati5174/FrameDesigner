"""
LLM ranking for fix suggestions.

This module is the ONLY place in framegen that imports LLM / Anthropic code.
It is never imported by generate, checks, outputs, or suggestions/__init__.py.
Only api.py imports it, and only when ANTHROPIC_API_KEY is present.

Contract:
  - rank_and_describe() receives a list of serialised FixCandidate dicts and
    the user's original request text.
  - It may reorder candidates. It must not add or drop any.
  - It writes one plain sentence per candidate into the "trade_off" field.
  - Every number in a sentence must appear verbatim in that candidate's
    verified data; if a sentence fails the guard it is replaced with the
    template text from the incoming dict.
  - If the LLM call fails for any reason, the original list is returned
    unchanged (template text preserved).
"""
from __future__ import annotations

import json
import os
import re


def _numbers_in(text: str) -> set[str]:
    """Return all digit sequences (normalised, no separators) found in text."""
    normalised = re.sub(r"[\s,_]", "", text)
    return set(re.findall(r"\d+(?:\.\d+)?", normalised))


def _numbers_allowed(sentence: str, candidate: dict) -> bool:  # type: ignore[type-arg]
    """
    Every number that appears in the sentence must also appear in the
    candidate dict (serialised as JSON, with thousands separators stripped).
    """
    allowed = _numbers_in(json.dumps(candidate))
    for num in _numbers_in(sentence):
        if num not in allowed:
            return False
    return True


def rank_and_describe(
    candidates: list[dict],  # type: ignore[type-arg]
    original_request: str,
) -> list[dict]:  # type: ignore[type-arg]
    """
    Return candidates reordered and with trade_off sentences from the LLM.
    Falls back to original list on any error.
    """
    if not candidates:
        return candidates

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return candidates

    try:
        import anthropic  # noqa: PLC0415
    except ImportError:
        return candidates

    # Build a compact summary for the prompt
    summaries = []
    for i, c in enumerate(candidates):
        summaries.append(
            f"{i}: fix_type={c['fix_type']}, trade_off={c['trade_off']!r}"
        )

    prompt = (
        "You are helping a user improve a frame design.\n\n"
        f"Original request: {original_request!r}\n\n"
        "The following fix candidates have been verified by the frame engine. "
        "Reorder them from most to least useful for this user, and replace each "
        "trade_off with ONE plain English sentence explaining the trade-off "
        "(no jargon, no bullet points, no lists). "
        "Only use numbers that appear in the candidate data below. "
        "Return JSON: a list of objects with keys 'index' (original index) and "
        "'trade_off' (your sentence). No other keys.\n\n"
        + "\n".join(summaries)
    )

    try:
        from framegen._llm_counter import check_and_increment  # noqa: PLC0415
        check_and_increment()
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        first = msg.content[0]
        raw = (first.text if hasattr(first, "text") else "").strip()
        # Strip code fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        ranked = json.loads(raw)
    except Exception:
        return candidates

    if not isinstance(ranked, list) or len(ranked) != len(candidates):
        return candidates

    result: list[dict] = []  # type: ignore[type-arg]
    seen_indices: set[int] = set()
    for item in ranked:
        if not isinstance(item, dict):
            return candidates
        idx = item.get("index")
        n = len(candidates)
        if not (isinstance(idx, int) and 0 <= idx < n and idx not in seen_indices):
            return candidates
        seen_indices.add(idx)
        sentence = item.get("trade_off", "")
        orig = candidates[idx]
        if not isinstance(sentence, str) or not _numbers_allowed(sentence, orig):
            sentence = orig["trade_off"]
        result.append({**orig, "trade_off": sentence})

    if len(result) != len(candidates):
        return candidates

    return result
