from __future__ import annotations

import dataclasses
import os
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from framegen.catalog import load_catalog
from framegen.checks import run_checks
from framegen.generate.shelf_unit import generate_shelf_unit
from framegen.generate.table import generate_table
from framegen.outputs.cut_list import build_cut_list
from framegen.parser import parse as parser_parse
from framegen.spec import ShelfUnitSpec, TableSpec
from framegen.suggestions import FixCandidate, suggest_fixes

load_dotenv(override=False)

_CATALOG = load_catalog()

app = FastAPI()


# ── /parse ────────────────────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    text: str = Field(..., max_length=500)


class SpecOut(BaseModel):
    """Unified spec representation for both tables and shelf units."""
    frame_type: Literal["table", "shelf_unit"] = "table"
    width_mm: float
    depth_mm: float
    height_mm: float
    profile_series: str
    # Table-only fields
    shelf_height_mm: float | None = None
    target_load_kg: float | None = None
    centre_legs: bool = False
    # Shelf-unit-only fields
    level_heights_mm: list[float] | None = None
    load_per_level_kg: float | None = None


class ParseResponse(BaseModel):
    outcome: Literal["spec_valid", "spec_invalid", "not_parsed"]
    spec: SpecOut | None
    error: str | None
    defaults_applied: list[str]
    parser_used: Literal["rule_based", "llm", "none"]
    llm_available: bool


def _spec_to_out(spec: TableSpec | ShelfUnitSpec) -> SpecOut:
    if isinstance(spec, ShelfUnitSpec):
        return SpecOut(
            frame_type="shelf_unit",
            width_mm=spec.width_mm,
            depth_mm=spec.depth_mm,
            height_mm=spec.height_mm,
            profile_series=spec.profile_series,
            level_heights_mm=spec.level_heights_mm,
            load_per_level_kg=spec.load_per_level_kg,
            centre_legs=spec.centre_legs,
        )
    return SpecOut(
        frame_type="table",
        width_mm=spec.width_mm,
        depth_mm=spec.depth_mm,
        height_mm=spec.height_mm,
        shelf_height_mm=spec.shelf_height_mm,
        profile_series=spec.profile_series,
        target_load_kg=spec.target_load_kg,
        centre_legs=spec.centre_legs,
    )


@app.post("/parse")
def post_parse(req: ParseRequest) -> ParseResponse:
    llm_available = bool(os.environ.get("ANTHROPIC_API_KEY"))
    result = parser_parse(req.text)
    spec_out: SpecOut | None = None
    if result.spec is not None:
        spec_out = _spec_to_out(result.spec)
    return ParseResponse(
        outcome=result.outcome,
        spec=spec_out,
        error=result.error,
        defaults_applied=result.defaults_applied,
        parser_used=result.parser_used,
        llm_available=llm_available,
    )


# ── Shared frame-generation logic ─────────────────────────────────────────────

def _run_frame(
    spec: TableSpec | ShelfUnitSpec,
    profile_series: str,
) -> dict[str, Any]:
    if profile_series not in _CATALOG.profiles:
        raise HTTPException(
            status_code=400, detail=f"unknown series: {profile_series!r}"
        )
    profile = _CATALOG.profiles[profile_series]

    try:
        if isinstance(spec, ShelfUnitSpec):
            bars = generate_shelf_unit(spec, profile)
        else:
            bars = generate_table(spec, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cut_list = build_cut_list(bars)
    check_report = run_checks(bars, spec, profile)
    suggestions = suggest_fixes(spec, profile, check_report)

    return {
        "bars": [
            {
                "start": [bar.start.x, bar.start.y, bar.start.z],
                "end": [bar.end.x, bar.end.y, bar.end.z],
                "profile_width_mm": profile.profile_width_mm,
                "role": bar.role,
            }
            for bar in bars
        ],
        "cut_list": [
            {
                "profile_id": row.profile_id,
                "length_mm": row.length_mm,
                "qty": row.qty,
                "total_mm": row.total_mm,
            }
            for row in cut_list.rows
        ],
        "check_report": dataclasses.asdict(check_report),
        "suggestions": [_serialise_candidate(c) for c in suggestions],
    }


# ── GET /frame (table only — kept for backwards compatibility) ────────────────

@app.get("/frame")
def get_frame(
    width: float = Query(...),
    depth: float = Query(...),
    height: float = Query(...),
    shelf: float | None = Query(default=None),
    series: str = Query(default="40-series"),
    load_kg: float = Query(default=100.0),
    centre_legs: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        spec = TableSpec.model_validate(
            dict(
                frame_type="table",
                width_mm=width,
                depth_mm=depth,
                height_mm=height,
                profile_series=series,
                target_load_kg=load_kg,
                shelf_height_mm=shelf,
                centre_legs=centre_legs,
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _run_frame(spec, series)


# ── POST /frame (both frame types) ───────────────────────────────────────────

class PostFrameRequest(BaseModel):
    spec: SpecOut


@app.post("/frame")
def post_frame(req: PostFrameRequest) -> dict[str, Any]:
    s = req.spec
    series = s.profile_series
    try:
        if s.frame_type == "shelf_unit":
            spec: TableSpec | ShelfUnitSpec = ShelfUnitSpec.model_validate(
                dict(
                    frame_type="shelf_unit",
                    width_mm=s.width_mm,
                    depth_mm=s.depth_mm,
                    height_mm=s.height_mm,
                    profile_series=series,
                    level_heights_mm=s.level_heights_mm or [],
                    load_per_level_kg=s.load_per_level_kg or 30.0,
                    centre_legs=s.centre_legs,
                )
            )
        else:
            spec = TableSpec.model_validate(
                dict(
                    frame_type="table",
                    width_mm=s.width_mm,
                    depth_mm=s.depth_mm,
                    height_mm=s.height_mm,
                    profile_series=series,
                    target_load_kg=s.target_load_kg or 100.0,
                    shelf_height_mm=s.shelf_height_mm,
                    centre_legs=s.centre_legs,
                )
            )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _run_frame(spec, series)


# ── /suggest ──────────────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    spec: SpecOut
    original_request: str = Field(default="", max_length=500)


@app.post("/suggest")
def post_suggest(req: SuggestRequest) -> dict[str, Any]:
    series = req.spec.profile_series
    if series not in _CATALOG.profiles:
        raise HTTPException(status_code=400, detail=f"unknown series: {series!r}")
    profile = _CATALOG.profiles[series]

    s = req.spec
    try:
        if s.frame_type == "shelf_unit":
            spec: TableSpec | ShelfUnitSpec = ShelfUnitSpec.model_validate(
                dict(
                    frame_type="shelf_unit",
                    width_mm=s.width_mm,
                    depth_mm=s.depth_mm,
                    height_mm=s.height_mm,
                    profile_series=series,
                    level_heights_mm=s.level_heights_mm or [],
                    load_per_level_kg=s.load_per_level_kg or 30.0,
                    centre_legs=s.centre_legs,
                )
            )
        else:
            spec = TableSpec.model_validate(
                dict(
                    frame_type="table",
                    width_mm=s.width_mm,
                    depth_mm=s.depth_mm,
                    height_mm=s.height_mm,
                    profile_series=series,
                    target_load_kg=s.target_load_kg or 100.0,
                    shelf_height_mm=s.shelf_height_mm,
                    centre_legs=s.centre_legs,
                )
            )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        if isinstance(spec, ShelfUnitSpec):
            bars = generate_shelf_unit(spec, profile)
        else:
            bars = generate_table(spec, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    check_report = run_checks(bars, spec, profile)
    candidates = suggest_fixes(spec, profile, check_report)
    serialised = [_serialise_candidate(c) for c in candidates]

    if serialised and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from framegen.suggestions.rank import rank_and_describe  # noqa: PLC0415
            serialised = rank_and_describe(serialised, req.original_request)
        except Exception:
            pass

    return {"suggestions": serialised}


# ── /edit ─────────────────────────────────────────────────────────────────────

class PartialSpecOut(BaseModel):
    frame_type: Literal["table", "shelf_unit"] | None = None
    width_mm: float | None = None
    depth_mm: float | None = None
    height_mm: float | None = None
    profile_series: str | None = None
    shelf_height_mm: float | None = None
    target_load_kg: float | None = None
    centre_legs: bool | None = None
    level_heights_mm: list[float] | None = None
    load_per_level_kg: float | None = None


class FieldChangeOut(BaseModel):
    field: str
    old: float | str | bool | list[float] | None = None
    new: float | str | bool | list[float] | None = None


class EditRequest(BaseModel):
    text: str = Field(..., max_length=500)
    spec: SpecOut | None = None
    pending: PartialSpecOut | None = None


class EditResponse(BaseModel):
    outcome: Literal[
        "new_design", "edit", "clarify",
        "unsupported", "spec_invalid", "not_parsed",
    ]
    spec: SpecOut | None = None
    pending: PartialSpecOut | None = None
    changes: list[FieldChangeOut] = []
    missing: list[str] = []
    defaults_applied: list[str] = []
    read_as: Literal["edit", "new_design"] | None = None
    parser_used: Literal["rule_based", "llm", "none"] = "none"
    llm_available: bool = False
    error: str | None = None


def _spec_out_to_internal(s: SpecOut) -> TableSpec | ShelfUnitSpec:
    if s.frame_type == "shelf_unit":
        return ShelfUnitSpec.model_validate(
            dict(
                frame_type="shelf_unit",
                width_mm=s.width_mm,
                depth_mm=s.depth_mm,
                height_mm=s.height_mm,
                profile_series=s.profile_series,
                level_heights_mm=s.level_heights_mm or [],
                load_per_level_kg=s.load_per_level_kg or 30.0,
                centre_legs=s.centre_legs,
            )
        )
    return TableSpec.model_validate(
        dict(
            frame_type="table",
            width_mm=s.width_mm,
            depth_mm=s.depth_mm,
            height_mm=s.height_mm,
            profile_series=s.profile_series,
            target_load_kg=s.target_load_kg or 100.0,
            shelf_height_mm=s.shelf_height_mm,
            centre_legs=s.centre_legs,
        )
    )


def _partial_out_to_internal(p: PartialSpecOut) -> Any:
    from framegen.parser.partial_spec import PartialSpec as _PS  # noqa: PLC0415
    return _PS(
        frame_type=p.frame_type,
        width_mm=p.width_mm,
        depth_mm=p.depth_mm,
        height_mm=p.height_mm,
        profile_series=p.profile_series,
        shelf_height_mm=p.shelf_height_mm,
        target_load_kg=p.target_load_kg,
        centre_legs=p.centre_legs,
        level_heights_mm=p.level_heights_mm,
        load_per_level_kg=p.load_per_level_kg,
    )


def _partial_internal_to_out(p: Any) -> PartialSpecOut:
    return PartialSpecOut(
        frame_type=p.frame_type,
        width_mm=p.width_mm,
        depth_mm=p.depth_mm,
        height_mm=p.height_mm,
        profile_series=p.profile_series,
        shelf_height_mm=p.shelf_height_mm,
        target_load_kg=p.target_load_kg,
        centre_legs=p.centre_legs,
        level_heights_mm=p.level_heights_mm,
        load_per_level_kg=p.load_per_level_kg,
    )


@app.post("/edit")
def post_edit(req: EditRequest) -> EditResponse:
    from framegen.parser.edit_dispatch import edit_parse  # noqa: PLC0415

    llm_available = bool(os.environ.get("ANTHROPIC_API_KEY"))

    spec_in: TableSpec | ShelfUnitSpec | None = None
    if req.spec is not None:
        try:
            spec_in = _spec_out_to_internal(req.spec)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    pending_in = None
    if req.pending is not None:
        pending_in = _partial_out_to_internal(req.pending)

    result = edit_parse(req.text, spec_in, pending_in)

    spec_out: SpecOut | None = None
    if result.spec is not None:
        spec_out = _spec_to_out(result.spec)

    pending_out: PartialSpecOut | None = None
    if result.pending is not None:
        pending_out = _partial_internal_to_out(result.pending)

    changes_out = [
        FieldChangeOut(field=c.field, old=c.old, new=c.new)
        for c in result.changes
    ]

    return EditResponse(
        outcome=result.outcome,
        spec=spec_out,
        pending=pending_out,
        changes=changes_out,
        missing=result.missing,
        defaults_applied=result.defaults_applied,
        read_as=result.read_as,
        parser_used=result.parser_used,
        llm_available=llm_available,
        error=result.error,
    )


def _serialise_candidate(c: FixCandidate) -> dict[str, Any]:
    spec = c.spec
    spec_dict: dict[str, Any]
    if isinstance(spec, ShelfUnitSpec):
        spec_dict = {
            "frame_type": "shelf_unit",
            "width_mm": spec.width_mm,
            "depth_mm": spec.depth_mm,
            "height_mm": spec.height_mm,
            "profile_series": spec.profile_series,
            "level_heights_mm": spec.level_heights_mm,
            "load_per_level_kg": spec.load_per_level_kg,
            "centre_legs": spec.centre_legs,
        }
    else:
        spec_dict = {
            "frame_type": "table",
            "width_mm": spec.width_mm,
            "depth_mm": spec.depth_mm,
            "height_mm": spec.height_mm,
            "shelf_height_mm": spec.shelf_height_mm,
            "profile_series": spec.profile_series,
            "target_load_kg": spec.target_load_kg,
            "centre_legs": spec.centre_legs,
        }
    return {
        "fix_type": c.fix_type,
        "spec": spec_dict,
        "check_report": dataclasses.asdict(c.check_report),
        "trade_off": c.trade_off,
        "resolves": c.resolves,
        "concentrated_warning_remains": c.concentrated_warning_remains,
    }
