from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

# ── Sanity limits ─────────────────────────────────────────────────────────────
# Guard against unit-conversion accidents (e.g. "750 metres" → 750 000 mm) and
# keep specs inside the range the generator and load check are designed for.
# Changing these values requires approval (see CLAUDE.md and ARCHITECTURE.md).
MAX_WIDTH_MM: float = 4000.0
MAX_DEPTH_MM: float = 2000.0
MAX_HEIGHT_MM: float = 2500.0
MAX_LOAD_KG: float = 2000.0

MAX_LEVEL_COUNT: int = 10
MIN_LEVEL_HEIGHT_MM: float = 150.0
MIN_LEVEL_SPACING_MM: float = 150.0


class TableSpec(BaseModel):
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


class ShelfUnitSpec(BaseModel):
    frame_type: Literal["shelf_unit"]
    width_mm: float
    depth_mm: float
    height_mm: float
    profile_series: str
    level_heights_mm: list[float]
    load_per_level_kg: float
    centre_legs: bool = False

    @model_validator(mode="after")
    def _check_valid(self) -> Self:
        if self.width_mm <= 0:
            raise ValueError("width_mm must be positive")
        if self.depth_mm <= 0:
            raise ValueError("depth_mm must be positive")
        if self.height_mm <= 0:
            raise ValueError("height_mm must be positive")
        if self.load_per_level_kg <= 0:
            raise ValueError("load_per_level_kg must be positive")
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
        if self.load_per_level_kg > MAX_LOAD_KG:
            raise ValueError(
                f"load_per_level_kg {self.load_per_level_kg:g} exceeds maximum"
                f" {MAX_LOAD_KG:g} kg — check the units"
            )

        lvls = self.level_heights_mm

        if len(lvls) < 3:
            raise ValueError(
                f"level_heights_mm must have at least 3 entries; got {len(lvls)}"
            )
        if len(lvls) > MAX_LEVEL_COUNT:
            raise ValueError(
                f"level_heights_mm has {len(lvls)} entries"
                f" — maximum is {MAX_LEVEL_COUNT}"
            )
        if lvls[-1] != self.height_mm:
            raise ValueError(
                f"last entry of level_heights_mm ({lvls[-1]:g}) must equal"
                f" height_mm ({self.height_mm:g})"
            )

        for i in range(1, len(lvls)):
            if lvls[i] <= lvls[i - 1]:
                raise ValueError(
                    f"level_heights_mm must be strictly ascending"
                    f" (entry {i} is {lvls[i]:g}, entry {i - 1} is {lvls[i - 1]:g})"
                )

        if lvls[0] < MIN_LEVEL_HEIGHT_MM:
            raise ValueError(
                f"first level height {lvls[0]:g} mm is below minimum"
                f" {MIN_LEVEL_HEIGHT_MM:g} mm"
            )

        for i in range(1, len(lvls)):
            gap = lvls[i] - lvls[i - 1]
            if gap < MIN_LEVEL_SPACING_MM:
                raise ValueError(
                    f"gap between levels {i} and {i + 1} is {gap:g} mm"
                    f" — minimum spacing is {MIN_LEVEL_SPACING_MM:g} mm"
                )

        return self


# Discriminated union — use for type annotations and TypeAdapter-based parsing.
# Concrete classes (TableSpec, ShelfUnitSpec) should be used directly when
# constructing instances or when a function handles only one frame type.
FrameSpec = Annotated[TableSpec | ShelfUnitSpec, Field(discriminator="frame_type")]
