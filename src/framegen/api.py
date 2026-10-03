from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from framegen.catalog import load_catalog
from framegen.checks import run_checks
from framegen.generate.table import generate_table
from framegen.outputs.cut_list import build_cut_list
from framegen.parser import parse as parser_parse
from framegen.spec import FrameSpec

# Load .env once at startup; variables already in the environment take precedence.
load_dotenv(override=False)

_CATALOG = load_catalog()
_REPO_ROOT = Path(__file__).parent.parent.parent
_WEB_DIR = _REPO_ROOT / "web"

app = FastAPI()


# ── /parse ────────────────────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    text: str = Field(..., max_length=500)


class SpecOut(BaseModel):
    width_mm: float
    depth_mm: float
    height_mm: float
    shelf_height_mm: float | None
    profile_series: str
    target_load_kg: float


class ParseResponse(BaseModel):
    outcome: Literal["spec_valid", "spec_invalid", "not_parsed"]
    spec: SpecOut | None
    error: str | None
    defaults_applied: list[str]
    parser_used: Literal["rule_based", "llm", "none"]
    llm_available: bool


@app.post("/parse")
def post_parse(req: ParseRequest) -> ParseResponse:
    llm_available = bool(os.environ.get("ANTHROPIC_API_KEY"))
    result = parser_parse(req.text)
    spec_out: SpecOut | None = None
    if result.spec is not None:
        spec_out = SpecOut(
            width_mm=result.spec.width_mm,
            depth_mm=result.spec.depth_mm,
            height_mm=result.spec.height_mm,
            shelf_height_mm=result.spec.shelf_height_mm,
            profile_series=result.spec.profile_series,
            target_load_kg=result.spec.target_load_kg,
        )
    return ParseResponse(
        outcome=result.outcome,
        spec=spec_out,
        error=result.error,
        defaults_applied=result.defaults_applied,
        parser_used=result.parser_used,
        llm_available=llm_available,
    )


# ── /frame ────────────────────────────────────────────────────────────────────

@app.get("/frame")
def get_frame(
    width: float = Query(...),
    depth: float = Query(...),
    height: float = Query(...),
    shelf: float | None = Query(default=None),
    series: str = Query(default="40-series"),
    load_kg: float = Query(default=100.0),
) -> dict[str, Any]:
    if series not in _CATALOG.profiles:
        raise HTTPException(status_code=400, detail=f"unknown series: {series!r}")

    profile = _CATALOG.profiles[series]

    try:
        spec = FrameSpec.model_validate(
            dict(
                frame_type="table",
                width_mm=width,
                depth_mm=depth,
                height_mm=height,
                profile_series=series,
                target_load_kg=load_kg,
                shelf_height_mm=shelf,
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        bars = generate_table(spec, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cut_list = build_cut_list(bars)
    check_report = run_checks(bars, spec, profile)

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
    }


app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
