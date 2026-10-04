"""
LLM-based edit parser for the /edit endpoint.

Called by the edit dispatcher when the rule parser returns not_matched.
The LLM sees only the current spec and the latest message (never the
full thread).  The 500-character cap is enforced by the caller (API).

Returns EditLlmResult with outcome:
  "operations"  — list of Operations to apply
  "new_design"  — user explicitly signals a new design
  "unsupported" — off-topic request
  "clarify"     — partial information; missing field names returned
  "not_matched" — LLM could not determine intent
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from framegen.parser.edit_rule import Operation
from framegen.spec import ShelfUnitSpec, TableSpec

# ── Client protocol (injectable for tests) ────────────────────────────────────

class _MessagesAPI(Protocol):
    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, str]],
        timeout: float,
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
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=api_key)  # type: ignore[assignment]
    except Exception:
        return None
    return _client


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class EditLlmResult:
    outcome: Literal[
        "operations", "new_design", "unsupported", "clarify", "not_matched"
    ]
    operations: list[Operation] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None


# ── Prompt ────────────────────────────────────────────────────────────────────

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 400
_TIMEOUT = 10.0
_FENCE_RE = re.compile(r"^```[a-z]*\n?|```$", re.MULTILINE)

_SYSTEM_TEMPLATE = """\
You help modify an aluminium-extrusion frame design based on a user instruction.

Current frame spec (JSON):
{spec_json}

Return ONLY a JSON object — no code fences, no explanation.

──────────────────────────────────────────────────────────────
1. Edit operations (most messages):
{{"operations": [{{"field": "<field>", "op": "set"|"add", "value": <value>}}, ...]}}

   Op rules:
   - "add": value is signed number (positive = increase, negative = decrease).
   - "set": value is new absolute value; null to clear (removes shelf).
   - centre_legs: set to true or false.
   - Convert measurements to mm (cm × 10, m × 1000).
   - Only return operations for fields the user mentioned.
   - "can it hold N kg" or "will it hold N kg" → set target_load_kg to N
     (NOT unsupported).

   For shelf unit levels use these special ops:
   - add_level:       {{"field": "level_heights_mm", "op": "add_level", "value": <mm>}}
   - remove_level:
       {{"field": "level_heights_mm", "op": "remove_level", "value": null}}
   - set_level_count:
       {{"field": "level_heights_mm", "op": "set_level_count", "value": <n>}}

   Fields for table:      width_mm, depth_mm, height_mm, shelf_height_mm,
                          target_load_kg, centre_legs
   Fields for shelf_unit: width_mm, depth_mm, height_mm, level_heights_mm,
                          load_per_level_kg, centre_legs

2. New design (user explicitly restarts: "start over", "from scratch", etc.):
{{"result": "new_design"}}

3. Off-topic (assembly, bolts, fasteners — NOT load questions):
{{"result": "unsupported", "reason": "<short reason>"}}

4. Missing information needed to complete the edit:
{{"result": "insufficient_information", "missing": ["<field>", ...]}}
──────────────────────────────────────────────────────────────
"""

_FIRST_TURN_SYSTEM = """\
You help parse a user's description of an aluminium-extrusion frame.

The user is starting fresh — there is no existing design yet.

Return ONLY a JSON object — no code fences, no explanation.

Return {{"result": "new_design"}} if you can identify enough for a complete
design, OR {{"result": "insufficient_information", "missing": ["<field>", ...]}}
if required fields (width_mm and/or depth_mm) are absent.

For off-topic requests (assembly, bolts):
{{"result": "unsupported", "reason": "..."}}
"""


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def _spec_to_json(spec: TableSpec | ShelfUnitSpec) -> str:
    if isinstance(spec, ShelfUnitSpec):
        d = {
            "frame_type": "shelf_unit",
            "width_mm": spec.width_mm,
            "depth_mm": spec.depth_mm,
            "height_mm": spec.height_mm,
            "level_heights_mm": spec.level_heights_mm,
            "load_per_level_kg": spec.load_per_level_kg,
            "centre_legs": spec.centre_legs,
        }
    else:
        d = {
            "frame_type": "table",
            "width_mm": spec.width_mm,
            "depth_mm": spec.depth_mm,
            "height_mm": spec.height_mm,
            "shelf_height_mm": spec.shelf_height_mm,
            "target_load_kg": spec.target_load_kg,
            "centre_legs": spec.centre_legs,
        }
    return json.dumps(d, indent=2)


def _call(
    client: _AnthropicClient,
    user_text: str,
    system: str,
) -> str:
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_text}],
        timeout=_TIMEOUT,
    )
    return resp.content[0].text  # type: ignore[no-any-return]


def _parse_operation(raw_op: dict[str, Any]) -> Operation | None:
    """Convert one LLM-returned operation dict to an Operation dataclass."""
    fld = raw_op.get("field")
    op = raw_op.get("op")
    value = raw_op.get("value")

    if not isinstance(fld, str) or not isinstance(op, str):
        return None

    if op not in ("set", "add", "add_level", "remove_level", "set_level_count"):
        return None

    # Normalise value types
    if op == "set":
        if value is None:
            typed_value: float | bool | None = None
        elif isinstance(value, bool):
            typed_value = value
        elif isinstance(value, (int, float)):
            typed_value = float(value)
        else:
            return None
    elif op in ("add", "add_level", "set_level_count"):
        if not isinstance(value, (int, float)):
            return None
        typed_value = float(value)
    else:  # remove_level
        typed_value = None

    return Operation(field=fld, op=op, value=typed_value)  # type: ignore[arg-type]


def _interpret(raw: str) -> EditLlmResult | None:
    """
    Parse the LLM response JSON.  Returns None if the response is
    malformed (triggers a retry).
    """
    text = _strip_fences(raw)
    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        return None

    result_key = data.get("result")

    if result_key == "new_design":
        return EditLlmResult(outcome="new_design")

    if result_key == "unsupported":
        reason = str(data.get("reason", "Unsupported request."))
        return EditLlmResult(outcome="unsupported", unsupported_reason=reason)

    if result_key == "insufficient_information":
        missing = data.get("missing", [])
        if not isinstance(missing, list):
            missing = []
        return EditLlmResult(outcome="clarify", missing=[str(m) for m in missing])

    if "operations" in data:
        ops_raw = data["operations"]
        if not isinstance(ops_raw, list):
            return None
        ops: list[Operation] = []
        for raw_op in ops_raw:
            if not isinstance(raw_op, dict):
                return None
            op = _parse_operation(raw_op)
            if op is None:
                return None
            ops.append(op)
        return EditLlmResult(outcome="operations", operations=ops)

    return None  # malformed — trigger retry


# ── Public functions ──────────────────────────────────────────────────────────

def parse_edit_with_spec(
    text: str,
    spec: TableSpec | ShelfUnitSpec,
) -> EditLlmResult:
    """
    LLM edit parser for the case where a current spec exists.
    Called when the rule parser returns not_matched.
    """
    client = _get_client()
    if client is None:
        return EditLlmResult(outcome="not_matched")

    system = _SYSTEM_TEMPLATE.format(spec_json=_spec_to_json(spec))

    try:
        raw = _call(client, text, system)
    except Exception:
        return EditLlmResult(outcome="not_matched")

    result = _interpret(raw)
    if result is None:
        # One retry with error context
        retry_system = system + (
            f"\n\nPrevious response was malformed: {raw!r}. "
            "Return only valid JSON."
        )
        try:
            raw = _call(client, text, retry_system)
        except Exception:
            return EditLlmResult(outcome="not_matched")
        result = _interpret(raw)

    return result if result is not None else EditLlmResult(outcome="not_matched")


def parse_first_turn(text: str) -> EditLlmResult:
    """
    LLM parser for the first turn (no existing spec, no pending).
    Returns new_design, clarify, unsupported, or not_matched.
    Note: actual spec construction is handled by the existing parse()
    function; this is used to extract partial info for clarify.
    """
    client = _get_client()
    if client is None:
        return EditLlmResult(outcome="not_matched")

    try:
        raw = _call(client, text, _FIRST_TURN_SYSTEM)
    except Exception:
        return EditLlmResult(outcome="not_matched")

    result = _interpret(raw)
    if result is None:
        return EditLlmResult(outcome="not_matched")
    return result
