from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, model_validator

# ── Sanity limits ─────────────────────────────────────────────────────────────
# Guard against unit-conversion accidents (e.g. "750 metres" → 750 000 mm) and
# keep specs inside the range the generator and load check are designed for.
# Changing these values requires approval (see CLAUDE.md and ARCHITECTURE.md).
MAX_WIDTH_MM: float = 4000.0
MAX_DEPTH_MM: float = 2000.0
MAX_HEIGHT_MM: float = 2500.0
MAX_LOAD_KG: float = 2000.0


class FrameSpec(BaseModel):
    frame_type: Literal["table"]
    width_mm: float
    depth_mm: float
    height_mm: float
    profile_series: str
    shelf_height_mm: float | None = None
    target_load_kg: float
    centre_legs: bool = False

    @model_validator(mode="after")
    def _check_positive(self) -> Self:
        if self.width_mm <= 0:
            raise ValueError("width_mm must be positive")
        if self.depth_mm <= 0:
            raise ValueError("depth_mm must be positive")
        if self.height_mm <= 0:
            raise ValueError("height_mm must be positive")
        if self.target_load_kg <= 0:
            raise ValueError("target_load_kg must be positive")
        if self.shelf_height_mm is not None:
            if self.shelf_height_mm <= 0:
                raise ValueError("shelf_height_mm must be positive")
            if self.shelf_height_mm >= self.height_mm:
                raise ValueError("shelf_height_mm must be less than height_mm")
        if self.width_mm > MAX_WIDTH_MM:
            raise ValueError(
                f"width_mm {self.width_mm:g} exceeds maximum {MAX_WIDTH_MM:g} mm"
                " — check the units"
            )
        if self.depth_mm > MAX_DEPTH_MM:
            raise ValueError(
                f"depth_mm {self.depth_mm:g} exceeds maximum {MAX_DEPTH_MM:g} mm"
                " — check the units"
            )
        if self.height_mm > MAX_HEIGHT_MM:
            raise ValueError(
                f"height_mm {self.height_mm:g} exceeds maximum {MAX_HEIGHT_MM:g} mm"
                " — check the units"
            )
        if self.target_load_kg > MAX_LOAD_KG:
            raise ValueError(
                f"target_load_kg {self.target_load_kg:g} exceeds maximum"
                f" {MAX_LOAD_KG:g} kg — check the units"
            )
        return self
