from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, model_validator


class FrameSpec(BaseModel):
    frame_type: Literal["table"]
    width_mm: float
    depth_mm: float
    height_mm: float
    profile_series: str
    shelf_height_mm: float | None = None
    target_load_kg: float

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
        return self
