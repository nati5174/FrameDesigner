"""
PartialSpec — an all-optional mirror of the frame spec fields.

Used by the /edit dispatcher to carry partial information across clarify
turns.  The API layer serialises it as PartialSpecOut (Pydantic).
FrameSpec, TableSpec, and ShelfUnitSpec are not changed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PartialSpec:
    frame_type: str | None = None
    width_mm: float | None = None
    depth_mm: float | None = None
    height_mm: float | None = None
    profile_series: str | None = None
    shelf_height_mm: float | None = None
    target_load_kg: float | None = None
    centre_legs: bool | None = None
    level_heights_mm: list[float] | None = None
    load_per_level_kg: float | None = None

    def missing_required(self) -> list[str]:
        """Return the names of required fields that are not yet set."""
        missing: list[str] = []
        if self.width_mm is None:
            missing.append("width_mm")
        if self.depth_mm is None:
            missing.append("depth_mm")
        return missing

    def to_context_text(self) -> str:
        """
        Convert known fields to a short text fragment so the rule-based
        parser can parse it together with a new user message.

        Example: "shelf unit, 1500 mm wide, 700 mm deep"
        """
        parts: list[str] = []
        if self.frame_type == "shelf_unit":
            parts.append("shelf unit")
        if self.width_mm is not None:
            parts.append(f"{self.width_mm:g} mm wide")
        if self.depth_mm is not None:
            parts.append(f"{self.depth_mm:g} mm deep")
        if self.height_mm is not None:
            parts.append(f"{self.height_mm:g} mm tall")
        if self.target_load_kg is not None:
            parts.append(f"holds {self.target_load_kg:g} kg")
        if self.load_per_level_kg is not None:
            parts.append(f"{self.load_per_level_kg:g} kg per level")
        return ", ".join(parts)
