from __future__ import annotations

import dataclasses
import json
import logging
import os
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response

from framegen import _llm_counter
from framegen._llm_counter import CAP_NOTE
from framegen.catalog import load_catalog
from framegen.checks import run_checks
from framegen.generate.shelf_unit import generate_shelf_unit
from framegen.generate.table import generate_table
from framegen.outputs.cut_list import build_cut_list
from framegen.outputs.cut_plan import (
    CutPlanPiece,
    CutPlanResult,
    ProfileCutPlan,
    StockBarPlan,
    plan_cuts,
)
from framegen.outputs.parts_list import build_parts_list
from framegen.outputs.step_export import export_step, step_filename
from framegen.parser import parse as parser_parse
from framegen.spec import ShelfUnitSpec, TableSpec
from framegen.suggestions import FixCandidate, suggest_cheaper_profile, suggest_fixes

load_dotenv(override=False)

_CATALOG = load_catalog()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


_GIT_COMMIT = _git_commit()

# Startup banner
print(
    f"framegen  catalog=v{_CATALOG.version}  commit={_GIT_COMMIT}",
    file=sys.stderr,
    flush=True,
)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(message)s")
_log = logging.getLogger("framegen")

# ── Rate limiter ──────────────────────────────────────────────────────────────


def _get_visitor_ip(request: Request) -> str:
    """
    Rate-limit key: leftmost value from X-Forwarded-For, or the direct
    client host when the header is absent.

    This is read directly from the header — not via uvicorn proxy flags —
    so it behaves identically under TestClient (pass XFF explicitly) and
    in production. A direct caller to the Render URL can spoof this by
    prepending fake IPs; the daily SDK-call cap is the backstop for that case.
    """
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_visitor_ip)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,  # type: ignore[arg-type]
)

# CORS — safe-fail default: no CORS if env var is absent
_ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "")
if _ALLOWED_ORIGIN:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_ALLOWED_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
else:
    print(
        "WARNING: ALLOWED_ORIGIN not set; CORS disabled",
        file=sys.stderr,
        flush=True,
    )


# ── Logging middleware ────────────────────────────────────────────────────────

@app.middleware("http")
async def _log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request.state.llm_called = False
    request.state.parser_used = None
    request.state.frame_type = None
    request.state.outcome = None

    t0 = time.monotonic()
    response = await call_next(request)
    ms = round((time.monotonic() - t0) * 1000)

    record: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "endpoint": request.url.path,
        "status": response.status_code,
        "latency_ms": ms,
        "llm_called": request.state.llm_called,
        "parser_used": request.state.parser_used,
        "frame_type": request.state.frame_type,
        "outcome": request.state.outcome,
    }
    _log.info(json.dumps(record))
    return response


# ── /health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def get_health() -> dict[str, Any]:
    return {
        "catalog_version": _CATALOG.version,
        "git_commit": _GIT_COMMIT,
    }


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
@limiter.limit("10/minute")
@limiter.limit("60/hour")
def post_parse(request: Request, req: ParseRequest) -> ParseResponse:
    llm_available = (
        bool(os.environ.get("ANTHROPIC_API_KEY")) and not _llm_counter.cap_reached()
    )
    result = parser_parse(req.text)
    spec_out: SpecOut | None = None
    if result.spec is not None:
        spec_out = _spec_to_out(result.spec)

    request.state.llm_called = result.parser_used == "llm"
    request.state.parser_used = result.parser_used
    request.state.outcome = result.outcome

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

    cut_list = build_cut_list(
        bars,
        price_per_mm=profile.price_per_mm,
        mass_per_metre_kg=profile.mass_per_metre_kg,
        cut_charge_usd=_CATALOG.cut_charge_usd,
    )
    parts = build_parts_list(bars, _CATALOG.connectors, profile_series)
    check_report = run_checks(bars, spec, profile)
    suggestions = suggest_fixes(spec, profile, check_report)
    cost_suggestion = suggest_cheaper_profile(
        spec, profile, check_report, _CATALOG,
        current_parts=parts,
    )

    hardware_cost = parts.hardware_cost_usd if parts.hardware_priced else None
    bars_cost = cut_list.total_cost_usd
    total_cost: float | None = (
        round(bars_cost + hardware_cost, 2)
        if bars_cost is not None and hardware_cost is not None
        else None
    )

    # Weight breakdown: bars + hardware
    bars_weight = cut_list.total_weight_kg
    hardware_weight = parts.hardware_weight_kg if parts.hardware_priced else None
    total_weight: float | None = (
        round(bars_weight + hardware_weight, 6)
        if bars_weight is not None and hardware_weight is not None
        else bars_weight
    )

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
                "cost_usd": row.cost_usd,
                "weight_kg": row.weight_kg,
            }
            for row in cut_list.rows
        ],
        "cut_list_total_cost_usd": cut_list.total_cost_usd,
        "cut_list_total_weight_kg": cut_list.total_weight_kg,
        "check_report": dataclasses.asdict(check_report),
        "suggestions": [_serialise_candidate(c) for c in suggestions],
        "cost_suggestion": (
            _serialise_candidate(cost_suggestion) if cost_suggestion else None
        ),
        "parts_list": [
            {
                "part_number": row.part_number,
                "description": row.description,
                "qty": row.qty,
                "unit_price_usd": row.unit_price_usd,
                "line_total_usd": row.line_total_usd,
                "source_url": row.source_url,
            }
            for row in parts.rows
        ],
        "hardware_cost_usd": hardware_cost,
        "hardware_weight_kg": hardware_weight,
        "total_cost_usd": total_cost,
        "total_weight_kg": total_weight,
        "hardware_priced": parts.hardware_priced,
    }


# ── GET /frame (table only — kept for backwards compatibility) ────────────────

@app.get("/frame")
@limiter.limit("120/minute")
def get_frame(
    request: Request,
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
        _log.error("validation_error in get_frame: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="I could not apply that change. The frame is unchanged.",
        ) from exc

    result = _run_frame(spec, series)
    request.state.frame_type = spec.frame_type
    request.state.outcome = "pass" if result["check_report"]["passed"] else "fail"
    return result


# ── POST /frame (both frame types) ───────────────────────────────────────────

class PostFrameRequest(BaseModel):
    spec: SpecOut


@app.post("/frame")
@limiter.limit("120/minute")
def post_frame(request: Request, req: PostFrameRequest) -> dict[str, Any]:
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
        _log.error("validation_error in post_frame: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="I could not apply that change. The frame is unchanged.",
        ) from exc

    result = _run_frame(spec, series)
    request.state.frame_type = spec.frame_type
    request.state.outcome = "pass" if result["check_report"]["passed"] else "fail"
    return result


# ── /suggest ──────────────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    spec: SpecOut
    original_request: str = Field(default="", max_length=500)


@app.post("/suggest")
@limiter.limit("10/minute")
@limiter.limit("60/hour")
def post_suggest(request: Request, req: SuggestRequest) -> dict[str, Any]:
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
        _log.error("validation_error in post_suggest: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="I could not apply that change. The frame is unchanged.",
        ) from exc

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

    request.state.frame_type = spec.frame_type

    if serialised and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from framegen.suggestions.rank import rank_and_describe  # noqa: PLC0415
            count_before = _llm_counter.get_count()
            serialised = rank_and_describe(serialised, req.original_request)
            request.state.llm_called = _llm_counter.get_count() > count_before
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
@limiter.limit("10/minute")
@limiter.limit("60/hour")
def post_edit(request: Request, req: EditRequest) -> EditResponse:
    from framegen.parser.edit_dispatch import edit_parse  # noqa: PLC0415

    llm_available = (
        bool(os.environ.get("ANTHROPIC_API_KEY")) and not _llm_counter.cap_reached()
    )

    spec_in: TableSpec | ShelfUnitSpec | None = None
    if req.spec is not None:
        try:
            spec_in = _spec_out_to_internal(req.spec)
        except ValidationError as exc:
            _log.error("validation_error in post_edit spec_in: %s", exc)
            raise HTTPException(
                status_code=400,
                detail="I could not apply that change. The frame is unchanged.",
            ) from exc

    pending_in = None
    if req.pending is not None:
        pending_in = _partial_out_to_internal(req.pending)

    result = edit_parse(req.text, spec_in, pending_in)

    # Add cap note when the LLM was skipped due to the daily cap
    error = result.error
    if (
        result.outcome == "not_parsed"
        and result.error is None
        and _llm_counter.cap_reached()
    ):
        error = CAP_NOTE

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

    request.state.llm_called = result.parser_used == "llm"
    request.state.parser_used = result.parser_used
    request.state.frame_type = result.spec.frame_type if result.spec else None
    request.state.outcome = result.outcome

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
        error=error,
    )


# ── /cut-plan ─────────────────────────────────────────────────────────────────

class CutPlanRequest(BaseModel):
    spec: SpecOut
    stock_length_mm: float = Field(default=3000.0, ge=500.0, le=8000.0)
    kerf_mm: float = Field(default=3.0, ge=0.0, le=10.0)


def _serialise_cut_plan(result: CutPlanResult) -> dict[str, Any]:
    def _piece(p: CutPlanPiece) -> dict[str, Any]:
        return {"length_mm": p.length_mm, "label": p.label}

    def _bar(b: StockBarPlan) -> dict[str, Any]:
        return {
            "pieces": [_piece(p) for p in b.pieces],
            "used_mm": b.used_mm,
            "offcut_mm": b.offcut_mm,
        }

    def _profile(pr: ProfileCutPlan) -> dict[str, Any]:
        return {
            "profile_id": pr.profile_id,
            "stock_bars": [_bar(b) for b in pr.stock_bars],
            "does_not_fit": [_piece(p) for p in pr.does_not_fit],
            "total_stock_bars": pr.total_stock_bars,
            "total_offcut_mm": pr.total_offcut_mm,
            "waste_pct": pr.waste_pct,
            "lower_bound_bars": pr.lower_bound_bars,
            "is_optimal": pr.is_optimal,
        }

    return {
        "profiles": [_profile(pr) for pr in result.profiles],
        "stock_length_mm": result.stock_length_mm,
        "kerf_mm": result.kerf_mm,
    }


@app.post("/cut-plan")
@limiter.limit("120/minute")
def post_cut_plan(request: Request, req: CutPlanRequest) -> dict[str, Any]:
    s = req.spec
    series = s.profile_series
    if series not in _CATALOG.profiles:
        raise HTTPException(status_code=400, detail=f"unknown series: {series!r}")
    profile = _CATALOG.profiles[series]

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
        _log.error("validation_error in post_cut_plan: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="I could not apply that change. The frame is unchanged.",
        ) from exc

    try:
        if isinstance(spec, ShelfUnitSpec):
            bars = generate_shelf_unit(spec, profile)
        else:
            bars = generate_table(spec, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = plan_cuts(bars, req.stock_length_mm, req.kerf_mm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    request.state.frame_type = spec.frame_type
    return _serialise_cut_plan(result)


# ── /export/step ──────────────────────────────────────────────────────────────

class ExportStepRequest(BaseModel):
    spec: SpecOut


@app.post("/export/step")
@limiter.limit("30/minute")
def post_export_step(request: Request, req: ExportStepRequest) -> Response:
    s = req.spec
    series = s.profile_series
    if series not in _CATALOG.profiles:
        raise HTTPException(status_code=400, detail=f"unknown series: {series!r}")
    profile = _CATALOG.profiles[series]

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
        _log.error("validation_error in post_export_step: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="I could not build a frame from that description. "
            "Please check the dimensions and try again.",
        ) from exc

    try:
        if isinstance(spec, ShelfUnitSpec):
            bars = generate_shelf_unit(spec, profile)
        else:
            bars = generate_table(spec, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    frame_type_label = spec.frame_type.replace("_", " ")
    design_name = (
        f"{frame_type_label} "
        f"{int(spec.width_mm)}x{int(spec.depth_mm)}x{int(spec.height_mm)}"
    )
    content = export_step(bars, profile.profile_width_mm, design_name)
    filename = step_filename(spec.width_mm, spec.depth_mm, spec.height_mm)

    request.state.frame_type = spec.frame_type
    request.state.outcome = "ok"

    return Response(
        content=content.encode("ascii"),
        media_type="model/step",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content.encode("ascii"))),
        },
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
