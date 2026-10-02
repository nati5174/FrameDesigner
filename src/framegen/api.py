from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from framegen.catalog import load_catalog
from framegen.generate.table import generate_table
from framegen.outputs.cut_list import build_cut_list
from framegen.spec import FrameSpec

_CATALOG = load_catalog()
_REPO_ROOT = Path(__file__).parent.parent.parent
_WEB_DIR = _REPO_ROOT / "web"

app = FastAPI()


@app.get("/frame")
def get_frame(
    width: float = Query(...),
    depth: float = Query(...),
    height: float = Query(...),
    shelf: float | None = Query(default=None),
    series: str = Query(default="40-series"),
    load_kg: float = Query(default=100.0),  # stored in spec; nothing uses it yet
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
    }


app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
