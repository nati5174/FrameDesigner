"""
Edit dispatcher — main entry point for POST /edit.

Routes to the correct handler based on (spec, pending) state, runs
pre-checks, applies operations, validates results, and builds the
EditResult that the API serialises.

Stage 1: rule-based path only.
Stage 2: LLM fallback added (see edit_llm.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import ValidationError

from framegen.parser.partial_spec import PartialSpec
from framegen.spec import ShelfUnitSpec, TableSpec

# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class FieldChange:
    field: str
    old: float | str | bool | list[float] | None
    new: float | str | bool | list[float] | None


@dataclass
class EditResult:
    outcome: Literal[
        "new_design", "edit", "clarify",
        "unsupported", "spec_invalid", "not_parsed",
    ]
    spec: TableSpec | ShelfUnitSpec | None = None
    pending: PartialSpec | None = None
    changes: list[FieldChange] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    defaults_applied: list[str] = field(default_factory=list)
    read_as: Literal["edit", "new_design"] | None = None
    parser_used: Literal["rule_based", "llm", "none"] = "none"
    error: str | None = None


# ── Unsupported detection ─────────────────────────────────────────────────────
# Runs after the rule parser returns not_matched.
# "can it hold N kg" is handled by the rule parser and never reaches this check.

_UNSUPPORTED_RE = re.compile(
    r"(?<!\w)(?:"
    r"what\s+bolts?|which\s+bolts?"
    r"|what\s+(?:angle\s+)?brackets?|which\s+brackets?"
    r"|how\s+do\s+i\s+(?:assemble|build|install|mount|attach)"
    r"|will\s+it\s+hold\s+a\s+\w"   # "will it hold a lathe" — not "hold 150"
    r"|what\s+fasteners?|which\s+fasteners?"
    r"|how\s+do\s+i\s+put\s+(?:it|this)\s+together"
    r"|is\s+it\s+safe\s+(?:to|for)"
    r"|how\s+long\s+will\s+it\s+last"
    r"|what\s+tools?\s+(?:do|will)\s+i\s+(?:need)"
    r"|how\s+heavy\s+is\s+(?:it|the)"
    r"|how\s+much\s+does\s+it\s+weigh"
    r")(?!\w)",
    re.IGNORECASE,
)

_UNSUPPORTED_MESSAGE = (
    "This tool designs aluminum extrusion frames. It can: set dimensions, "
    "add a shelf, check load capacity, suggest size or load adjustments. "
    "It cannot give assembly, fastener, or general engineering advice."
)


def _is_unsupported(text: str) -> bool:
    return bool(_UNSUPPORTED_RE.search(text))


# ── Spec ↔ dict helpers ───────────────────────────────────────────────────────

_FRAME_FIELDS: dict[str, set[str]] = {
    "table": {
        "width_mm", "depth_mm", "height_mm",
        "shelf_height_mm", "target_load_kg", "centre_legs",
    },
    "shelf_unit": {
        "width_mm", "depth_mm", "height_mm",
        "level_heights_mm", "load_per_level_kg", "centre_legs",
    },
}

# Fields that may be set to None (i.e. cleared)
_NULLABLE_FIELDS = {"shelf_height_mm"}


def _spec_to_dict(spec: TableSpec | ShelfUnitSpec) -> dict:  # type: ignore[type-arg]
    if isinstance(spec, ShelfUnitSpec):
        return {
            "frame_type": "shelf_unit",
            "width_mm": spec.width_mm,
            "depth_mm": spec.depth_mm,
            "height_mm": spec.height_mm,
            "profile_series": spec.profile_series,
            "level_heights_mm": list(spec.level_heights_mm),
            "load_per_level_kg": spec.load_per_level_kg,
            "centre_legs": spec.centre_legs,
        }
    return {
        "frame_type": "table",
        "width_mm": spec.width_mm,
        "depth_mm": spec.depth_mm,
        "height_mm": spec.height_mm,
        "profile_series": spec.profile_series,
        "shelf_height_mm": spec.shelf_height_mm,
        "target_load_kg": spec.target_load_kg,
        "centre_legs": spec.centre_legs,
    }


def _dict_to_spec(d: dict) -> TableSpec | ShelfUnitSpec:  # type: ignore[type-arg]
    if d.get("frame_type") == "shelf_unit":
        return ShelfUnitSpec.model_validate(d)
    return TableSpec.model_validate(d)


def _build_changes(
    old: dict,  # type: ignore[type-arg]
    new: dict,  # type: ignore[type-arg]
) -> list[FieldChange]:
    changes: list[FieldChange] = []
    all_fields = sorted(set(old) | set(new))
    for f in all_fields:
        o = old.get(f)
        n = new.get(f)
        if o != n:
            changes.append(FieldChange(field=f, old=o, new=n))
    return changes


# ── Evenly-spaced level helper ────────────────────────────────────────────────

def _evenly_spaced_levels(H: float, n: int) -> list[float]:
    levels = [float(round(H * (i + 1) / n)) for i in range(n)]
    levels[-1] = H
    return levels


# ── Operation application ─────────────────────────────────────────────────────

from framegen.parser.edit_rule import (  # noqa: E402
    Operation,
)


def _apply_op(d: dict, op: Operation) -> str | None:  # type: ignore[type-arg]
    """
    Apply a single operation to the spec dict in-place.
    Returns an error string on failure, None on success.
    """
    fld = op.field
    frame_type = d.get("frame_type", "table")
    valid = _FRAME_FIELDS.get(frame_type, set())

    if fld not in valid:
        return f"Field '{fld}' does not apply to {frame_type} frames"

    current = d.get(fld)

    if op.op == "set":
        if op.value is None and fld not in _NULLABLE_FIELDS:
            return f"Cannot clear '{fld}'"
        d[fld] = op.value
        return None

    if op.op == "add":
        if current is None:
            return f"Cannot add to '{fld}': current value is not set"
        if not isinstance(current, (int, float)):
            return f"Cannot add to '{fld}': not a numeric field"
        d[fld] = current + float(op.value)  # type: ignore[operator,arg-type]
        return None

    if op.op == "add_level":
        if not isinstance(current, list):
            return "No level list to add to"
        new_h = float(op.value)  # type: ignore[arg-type]
        if any(abs(h - new_h) < 1.0 for h in current):
            return f"A level at {new_h:g} mm already exists"
        d[fld] = sorted(current + [new_h])
        return None

    if op.op == "remove_level":
        if not isinstance(current, list):
            return "No level list to remove from"
        if len(current) <= 3:
            return "Cannot remove level: minimum 3 levels required"
        # Remove the second-to-last entry ([-2]); [-1] = height_mm stays
        d[fld] = current[:-2] + [current[-1]]
        return None

    if op.op == "set_level_count":
        n = int(op.value)  # type: ignore[arg-type]
        H = d.get("height_mm")
        if H is None:
            return "Cannot set level count: height_mm is not set"
        d[fld] = _evenly_spaced_levels(float(H), n)
        return None

    return f"Unknown operation type: {op.op!r}"


def _apply_and_return(
    ops: list[Operation],
    old_spec: TableSpec | ShelfUnitSpec,
    parser_used: str,
) -> EditResult:
    old_dict = _spec_to_dict(old_spec)
    new_dict = _spec_to_dict(old_spec)  # mutable copy

    for op in ops:
        err = _apply_op(new_dict, op)
        if err:
            return EditResult(
                outcome="spec_invalid",
                error=err,
                parser_used=parser_used,  # type: ignore[arg-type]
            )

    changes = _build_changes(old_dict, new_dict)

    try:
        new_spec = _dict_to_spec(new_dict)
    except ValidationError as exc:
        msgs = "; ".join(e["msg"] for e in exc.errors())
        return EditResult(
            outcome="spec_invalid",
            error=msgs,
            parser_used=parser_used,  # type: ignore[arg-type]
        )

    return EditResult(
        outcome="edit",
        spec=new_spec,
        changes=changes,
        read_as="edit",
        parser_used=parser_used,  # type: ignore[arg-type]
    )


# ── Frame-type migration helper ───────────────────────────────────────────────

def _migrate_type(
    old_spec: TableSpec | ShelfUnitSpec,
    new_spec: TableSpec | ShelfUnitSpec,
    new_defaults: list[str],
) -> EditResult:
    """Return a new_design EditResult that records the type change."""
    old_dict = _spec_to_dict(old_spec)
    new_dict = _spec_to_dict(new_spec)
    changes = _build_changes(old_dict, new_dict)
    return EditResult(
        outcome="new_design",
        spec=new_spec,
        changes=changes,
        read_as="new_design",
        defaults_applied=new_defaults,
        parser_used="rule_based",
    )


# ── LLM bridges ───────────────────────────────────────────────────────────────


def _llm_first_turn(text: str) -> EditResult:
    """LLM fallback for the first turn (rule parser returned not_parsed)."""
    from framegen.parser.edit_llm import parse_first_turn

    result = parse_first_turn(text)

    if result.outcome == "unsupported":
        return EditResult(
            outcome="unsupported",
            error=result.unsupported_reason or _UNSUPPORTED_MESSAGE,
            parser_used="llm",
        )
    if result.outcome == "clarify":
        return EditResult(
            outcome="clarify",
            missing=result.missing,
            parser_used="llm",
        )
    # new_design or not_matched — rule parser already failed; can't build spec
    return EditResult(outcome="not_parsed", parser_used="none")


def _llm_edit(
    text: str,
    spec: TableSpec | ShelfUnitSpec,
) -> EditResult:
    """LLM fallback when the rule edit parser returned not_matched."""
    from framegen.parser.edit_llm import parse_edit_with_spec

    result = parse_edit_with_spec(text, spec)

    if result.outcome == "operations":
        return _apply_and_return(result.operations, spec, "llm")

    if result.outcome == "new_design":
        from framegen.parser import parse
        parse_result = parse(text)
        if parse_result.outcome == "spec_valid" and parse_result.spec is not None:
            new_spec = parse_result.spec
            if new_spec.frame_type != spec.frame_type:
                return _migrate_type(spec, new_spec, parse_result.defaults_applied)
            old_dict = _spec_to_dict(spec)
            new_dict = _spec_to_dict(new_spec)
            changes = _build_changes(old_dict, new_dict)
            return EditResult(
                outcome="new_design",
                spec=new_spec,
                changes=changes,
                read_as="new_design",
                defaults_applied=parse_result.defaults_applied,
                parser_used=parse_result.parser_used,
            )
        return EditResult(outcome="not_parsed", parser_used="none")

    if result.outcome == "unsupported":
        return EditResult(
            outcome="unsupported",
            error=result.unsupported_reason or _UNSUPPORTED_MESSAGE,
            parser_used="llm",
        )

    if result.outcome == "clarify":
        return EditResult(
            outcome="clarify",
            missing=result.missing,
            parser_used="llm",
        )

    return EditResult(outcome="not_parsed", parser_used="none")


# ── Turn handlers ─────────────────────────────────────────────────────────────

def _handle_first_turn(text: str) -> EditResult:
    """No existing spec, no pending partial — parse as a new design."""
    from framegen.parser import parse  # avoid circular import at module level

    result = parse(text)
    if result.outcome == "spec_valid" and result.spec is not None:
        return EditResult(
            outcome="new_design",
            spec=result.spec,
            read_as="new_design",
            defaults_applied=result.defaults_applied,
            parser_used=result.parser_used,
        )
    if result.outcome == "spec_invalid":
        return EditResult(
            outcome="spec_invalid",
            error=result.error,
            parser_used=result.parser_used,
        )
    # not_parsed — check unsupported, then LLM
    if _is_unsupported(text):
        return EditResult(
            outcome="unsupported",
            error=_UNSUPPORTED_MESSAGE,
            parser_used="none",
        )
    return _llm_first_turn(text)


def _handle_clarify(text: str, pending: PartialSpec) -> EditResult:
    """
    A prior turn returned 'clarify'.  The client has sent the stored
    partial back together with the user's follow-up text.
    """
    from framegen.parser import parse

    # Try the text alone first — the user may have given everything needed
    result = parse(text)
    if result.outcome == "spec_valid" and result.spec is not None:
        return EditResult(
            outcome="new_design",
            spec=result.spec,
            read_as="new_design",
            defaults_applied=result.defaults_applied,
            parser_used=result.parser_used,
        )

    # Try merging the pending context with the new text
    context = pending.to_context_text()
    if context:
        combined = context + ", " + text
        result2 = parse(combined)
        if result2.outcome == "spec_valid" and result2.spec is not None:
            return EditResult(
                outcome="new_design",
                spec=result2.spec,
                read_as="new_design",
                defaults_applied=result2.defaults_applied,
                parser_used=result2.parser_used,
            )
        if result2.outcome == "spec_invalid":
            return EditResult(
                outcome="spec_invalid",
                error=result2.error,
                parser_used=result2.parser_used,
            )

    if _is_unsupported(text):
        return EditResult(
            outcome="unsupported",
            error=_UNSUPPORTED_MESSAGE,
            parser_used="none",
        )

    # LLM with pending context: synthesise a temporary spec if possible
    # and use the edit LLM; if not possible fall back to not_parsed
    return EditResult(outcome="not_parsed", parser_used="none")


def _handle_edit_or_new(
    text: str, spec: TableSpec | ShelfUnitSpec
) -> EditResult:
    """Existing spec present — default is edit, detect new-design signals."""
    from framegen.parser import parse
    from framegen.parser.edit_rule import parse_edit

    rule_result = parse_edit(text)

    if rule_result.outcome == "new_design":
        # Parse the text as a new design
        parse_result = parse(text)
        if parse_result.outcome == "spec_valid" and parse_result.spec is not None:
            new_spec = parse_result.spec
            if new_spec.frame_type != spec.frame_type:
                return _migrate_type(spec, new_spec, parse_result.defaults_applied)
            old_dict = _spec_to_dict(spec)
            new_dict = _spec_to_dict(new_spec)
            changes = _build_changes(old_dict, new_dict)
            return EditResult(
                outcome="new_design",
                spec=new_spec,
                changes=changes,
                read_as="new_design",
                defaults_applied=parse_result.defaults_applied,
                parser_used=parse_result.parser_used,
            )
        if parse_result.outcome == "spec_invalid":
            return EditResult(
                outcome="spec_invalid",
                error=parse_result.error,
                parser_used=parse_result.parser_used,
            )
        # not_parsed after new_design signal: stage 2 LLM
        return EditResult(outcome="not_parsed", parser_used="none")

    if rule_result.outcome == "operations":
        return _apply_and_return(rule_result.operations, spec, "rule_based")

    # not_matched — check unsupported, then LLM
    if _is_unsupported(text):
        return EditResult(
            outcome="unsupported",
            error=_UNSUPPORTED_MESSAGE,
            parser_used="none",
        )

    return _llm_edit(text, spec)


# ── Public entry point ────────────────────────────────────────────────────────

def edit_parse(
    text: str,
    spec_in: TableSpec | ShelfUnitSpec | None,
    pending_in: PartialSpec | None,
) -> EditResult:
    """
    Main entry point for POST /edit.

    Args:
        text:       User's message (≤ 500 chars; caller enforces cap).
        spec_in:    Current complete design, or None on the first turn.
        pending_in: Partial spec from a prior clarify turn, or None.

    Returns an EditResult; the API converts it to an EditResponse.
    """
    from framegen.parser import _check_enclosure, _check_imperial

    imp_err = _check_imperial(text)
    if imp_err:
        return EditResult(outcome="spec_invalid", error=imp_err, parser_used="none")

    enc_err = _check_enclosure(text)
    if enc_err:
        return EditResult(outcome="spec_invalid", error=enc_err, parser_used="none")

    if spec_in is None and pending_in is None:
        return _handle_first_turn(text)

    if spec_in is None and pending_in is not None:
        return _handle_clarify(text, pending_in)

    # spec_in is not None (may or may not have pending; pending is ignored when
    # a full spec is present)
    assert spec_in is not None
    return _handle_edit_or_new(text, spec_in)
