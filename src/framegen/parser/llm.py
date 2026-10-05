from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol

from pydantic import ValidationError

from framegen._llm_counter import CAP_NOTE, DailyCapReached, check_and_increment
from framegen.parser import _TABLE_WORD_RE, ParseResult
from framegen.spec import ShelfUnitSpec, TableSpec

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
_client_set_explicitly: bool = False


def set_client(client: _AnthropicClient | None) -> None:
    global _client, _client_set_explicitly
    _client = client
    _client_set_explicitly = True


def _get_client() -> _AnthropicClient | None:
    global _client
    if _client_set_explicitly:
        return _client
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

Frame types:
  "table"      — single work surface (bench, desk, stand, workbench)
  "shelf_unit" — multiple shelves or levels (bookcase, shelving, rack, storage unit)

A shelf unit requires an explicit signal: words like "shelf unit", "shelving",
"bookcase", "bookshelf", "rack", "racking", "3 levels", "4 shelves", etc.
A request with a single shelf at one height is a TABLE, not a shelf unit.

──────────────────────────────────────────────────────────────────
For a TABLE return:
{
  "frame_type": "table",
  "width_mm": <number>,
  "depth_mm": <number>,
  "height_mm": <number | null>,
  "shelf_height_mm": <number | null>,
  "target_load_kg": <number | null>,
  "centre_legs": <true | false | null>
}

For a SHELF UNIT return:
{
  "frame_type": "shelf_unit",
  "width_mm": <number>,
  "depth_mm": <number>,
  "height_mm": <number | null>,
  "level_heights_mm": <sorted list of 3–10 numbers | null>,
  "load_per_level_kg": <number | null>,
  "centre_legs": <true | false | null>
}
──────────────────────────────────────────────────────────────────

Rules:
- centre_legs: true if user says "centre legs", "center legs", "middle legs",
  "middle support", etc. false or null if not mentioned (defaults to false).
- Convert all measurements to millimetres (cm × 10, m × 1000).
- Return null for height_mm if the user did not state it; the caller applies
  the correct default based on the wording.
- For a shelf unit, level_heights_mm must be sorted ascending, last value
  must equal height_mm, minimum 3 entries. If the user gives explicit
  heights, use them (add height_mm as the last entry if missing).
  If not given, space levels evenly: e.g. 4 levels at height 2000 mm →
  [500, 1000, 1500, 2000].
- Return null for level_heights_mm when height_mm is also null (the caller
  will compute levels after applying the height default).
- If a dimension value is a bare number under 100 with no unit,
  return {"result": "unsupported",
          "reason": "Unitless number is ambiguous (mm, cm, or m?). \
Please add units."}.
- If you cannot determine width and depth,
  return {"result": "insufficient_information"}.
- If the request is for an enclosure or cabinet (not an open frame), return
  {"result": "unsupported",
   "reason": "Enclosures are not supported; only open frames."}.
- If imperial units are given, return
  {"result": "unsupported",
   "reason": "Imperial units are not supported. Please use mm, cm, or m."}.
"""

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 400
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
    check_and_increment()
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
    """Turn model raw text into a ParseResult. Does NOT materialise FrameSpec."""
    text = _strip_fences(raw)
    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        return _NOT_PARSED

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

    if "width_mm" not in data or "depth_mm" not in data:
        return _NOT_PARSED

    return ParseResult(outcome="spec_valid", spec=None, error=None, parser_used="llm")


def _materialise(data: dict[str, Any], original_text: str) -> ParseResult:  # noqa: C901
    """Build a TableSpec or ShelfUnitSpec from already-validated JSON data."""
    defaults: list[str] = []
    frame_type = data.get("frame_type", "table")

    if frame_type == "shelf_unit":
        height_mm = data.get("height_mm")
        if height_mm is None:
            # Apply wording-based default: table word → 900, else → 1800.
            height_mm = 900.0 if _TABLE_WORD_RE.search(original_text) else 1800.0
            defaults.append(f"height_mm={int(height_mm)}")

        level_heights_mm = data.get("level_heights_mm")
        if level_heights_mm is None:
            # Default: 3 evenly spaced levels
            n = 3
            level_heights_mm = [round(height_mm * (i + 1) / n) for i in range(n)]
            level_heights_mm[-1] = height_mm
            defaults.append("level_heights_mm=default_3_levels")

        load_per_level = data.get("load_per_level_kg")
        if load_per_level is None:
            load_per_level = 30.0
            defaults.append("load_per_level_kg=30")

        centre_legs = bool(data["centre_legs"]) if data.get("centre_legs") else False

        try:
            spec: ShelfUnitSpec | TableSpec = ShelfUnitSpec.model_validate(
                dict(
                    frame_type="shelf_unit",
                    width_mm=data["width_mm"],
                    depth_mm=data["depth_mm"],
                    height_mm=height_mm,
                    profile_series="40-series",
                    level_heights_mm=level_heights_mm,
                    load_per_level_kg=load_per_level,
                    centre_legs=centre_legs,
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

    # ── Table ─────────────────────────────────────────────────────────────────
    height_mm = data.get("height_mm")
    if height_mm is None:
        height_mm = 900.0
        defaults.append("height_mm=900")

    load_kg = data.get("target_load_kg")
    if load_kg is None:
        load_kg = 100.0
        defaults.append("target_load_kg=100")

    shelf_height = data.get("shelf_height_mm")
    centre_legs = bool(data.get("centre_legs")) if data.get("centre_legs") else False

    try:
        spec = TableSpec.model_validate(
            dict(
                frame_type="table",
                width_mm=data["width_mm"],
                depth_mm=data["depth_mm"],
                height_mm=height_mm,
                profile_series="40-series",
                target_load_kg=load_kg,
                shelf_height_mm=shelf_height,
                centre_legs=centre_legs,
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


def parse(text: str) -> ParseResult:
    """
    LLM-based parser. Pre-checks have already run in the dispatcher.

    Retry logic:
      - Malformed / missing-field response → 1 retry.
      - FrameSpec validation failure → spec_invalid, no retry.
    """
    client = _get_client()
    if client is None:
        return _NOT_PARSED

    user_text = text[:_INPUT_CAP]

    try:
        raw = _call(client, user_text)
    except DailyCapReached:
        return ParseResult(
            outcome="not_parsed",
            spec=None,
            error=CAP_NOTE,
            parser_used="rule_based",
        )
    except Exception:
        return ParseResult(
            outcome="not_parsed",
            spec=None,
            error=_LLM_ERROR,
            parser_used="llm",
        )

    result = _interpret(raw)

    if result.outcome == "not_parsed":
        retry_system = (
            "\n\nPrevious response was not valid JSON or was missing required fields. "
            f"Raw response was: {raw!r}. Please return only a valid JSON object."
        )
        try:
            raw = _call(client, user_text, extra_system=retry_system)
        except DailyCapReached:
            return ParseResult(
                outcome="not_parsed",
                spec=None,
                error=CAP_NOTE,
                parser_used="rule_based",
            )
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

    if result.outcome == "spec_invalid":
        return result

    text_stripped = _strip_fences(raw)
    try:
        data: dict[str, Any] = json.loads(text_stripped)
    except json.JSONDecodeError:
        return _NOT_PARSED

    return _materialise(data, user_text)
