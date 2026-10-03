from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

from pydantic import ValidationError

from framegen.parser import ParseResult
from framegen.spec import FrameSpec

# ── Client protocol (injectable for tests) ────────────────────────────────────

class _MessagesAPI(Protocol):
    def create(
        self, *, model: str, max_tokens: int, system: str,
        messages: list[dict[str, str]], timeout: float
    ) -> Any:
        ...


class _AnthropicClient(Protocol):
    @property
    def messages(self) -> _MessagesAPI:
        ...


_client: _AnthropicClient | None = None
# When True, _get_client() returns _client as-is (even if None) instead of
# attempting auto-initialisation from the environment. Set by set_client().
_client_set_explicitly: bool = False


def set_client(client: _AnthropicClient | None) -> None:
    """Override the Anthropic client — used in tests to inject a mock.
    Passing None disables auto-init from the environment until the flag is reset.
    """
    global _client, _client_set_explicitly
    _client = client
    _client_set_explicitly = True


def _get_client() -> _AnthropicClient | None:
    global _client
    if _client_set_explicitly:
        return _client  # explicit override: respect None as "no client"
    if _client is not None:
        return _client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=api_key)  # type: ignore[assignment]
    except Exception:
        return None
    return _client


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You convert a user's description of an aluminium-extrusion frame into JSON.

Return ONLY a JSON object — no code fences, no explanation.

If you can extract the dimensions, return:
{
  "width_mm": <number>,
  "depth_mm": <number>,
  "height_mm": <number | null>,
  "shelf_height_mm": <number | null>,
  "target_load_kg": <number | null>
}

Rules:
- Convert all measurements to millimetres (cm × 10, m × 1000).
- If height is not mentioned, return null (the caller will apply a default).
- If load is not mentioned, return null (the caller will apply a default).
- If no shelf is mentioned, shelf_height_mm must be null.
- If a dimension value is a bare number under 100 with no unit (e.g. "50 x 70 x 90"),
  return {"result": "unsupported",
          "reason": "Unitless number is ambiguous (mm, cm, or m?). Please add units."}.
- If you cannot determine width and depth,
  return {"result": "insufficient_information"}.
- If the request is for an enclosure or cabinet (not an open frame), return
  {"result": "unsupported", "reason": "Enclosures are not supported; only open frames."
  }.
- If imperial units are given (inches, feet), return
  {"result": "unsupported",
   "reason": "Imperial units are not supported. Please use mm, cm, or m."}.
"""

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 256
_INPUT_CAP = 500
_TIMEOUT = 10.0

_FENCE_RE = re.compile(r'^```[a-z]*\n?|```$', re.MULTILINE)

_NOT_PARSED = ParseResult(
    outcome="not_parsed", spec=None, error=None, parser_used="llm"
)

_LLM_ERROR = (
    "The LLM could not be reached (timeout or network error). "
    "Try again, or enter dimensions directly in the form."
)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _call(client: _AnthropicClient, user_text: str, extra_system: str = "") -> str:
    system = _SYSTEM + extra_system
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_text}],
        timeout=_TIMEOUT,
    )
    return resp.content[0].text  # type: ignore[no-any-return]


def _interpret(raw: str) -> ParseResult:
    """Turn model raw text into a ParseResult. Does NOT do FrameSpec validation."""
    text = _strip_fences(raw)
    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        return _NOT_PARSED  # signal: retry

    # Explicit result keys
    result_key = data.get("result")
    if result_key == "insufficient_information":
        return _NOT_PARSED
    if result_key == "unsupported":
        return ParseResult(
            outcome="spec_invalid",
            spec=None,
            error=str(data.get("reason", "Unsupported request.")),
            parser_used="llm",
        )

    # Must have at least width_mm and depth_mm
    if "width_mm" not in data or "depth_mm" not in data:
        return _NOT_PARSED  # signal: retry

    return ParseResult(outcome="spec_valid", spec=None, error=None, parser_used="llm")


def parse(text: str) -> ParseResult:
    """
    LLM-based parser. Pre-checks have already run in the dispatcher.

    Retry logic:
      - Malformed / missing-field response → 1 retry including the error.
      - FrameSpec validation failure → spec_invalid immediately, no retry.
    Error handling:
      - Network / timeout / auth errors → not_parsed with error message.
    """
    client = _get_client()
    if client is None:
        return _NOT_PARSED

    user_text = text[:_INPUT_CAP]

    # First attempt
    try:
        raw = _call(client, user_text)
    except Exception:
        return ParseResult(
            outcome="not_parsed",
            spec=None,
            error=_LLM_ERROR,
            parser_used="llm",
        )

    result = _interpret(raw)

    # Retry once on malformed/missing-field response
    if result.outcome == "not_parsed":
        retry_system = (
            "\n\nPrevious response was not valid JSON or was missing required fields. "
            f"Raw response was: {raw!r}. Please return only a valid JSON object."
        )
        try:
            raw = _call(client, user_text, extra_system=retry_system)
        except Exception:
            return ParseResult(
                outcome="not_parsed",
                spec=None,
                error=_LLM_ERROR,
                parser_used="llm",
            )
        result = _interpret(raw)
        if result.outcome == "not_parsed":
            return _NOT_PARSED

    # If interpret flagged spec_invalid already, return it
    if result.outcome == "spec_invalid":
        return result

    # Now materialise FrameSpec from the parsed JSON (use the winning `raw`)
    text_stripped = _strip_fences(raw)
    try:
        data: dict[str, Any] = json.loads(text_stripped)
    except json.JSONDecodeError:
        return _NOT_PARSED

    defaults: list[str] = []

    height_mm = data.get("height_mm")
    if height_mm is None:
        height_mm = 900.0
        defaults.append("height_mm=900")

    load_kg = data.get("target_load_kg")
    if load_kg is None:
        load_kg = 100.0
        defaults.append("target_load_kg=100")

    shelf_height = data.get("shelf_height_mm")

    try:
        spec = FrameSpec.model_validate(
            dict(
                frame_type="table",
                width_mm=data["width_mm"],
                depth_mm=data["depth_mm"],
                height_mm=height_mm,
                profile_series="40-series",
                target_load_kg=load_kg,
                shelf_height_mm=shelf_height,
            )
        )
    except ValidationError as exc:
        msgs = "; ".join(e["msg"] for e in exc.errors())
        return ParseResult(
            outcome="spec_invalid",
            spec=None,
            error=msgs,
            parser_used="llm",
        )

    return ParseResult(
        outcome="spec_valid",
        spec=spec,
        error=None,
        defaults_applied=defaults,
        parser_used="llm",
    )
