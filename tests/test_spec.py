from __future__ import annotations

import pytest
from pydantic import ValidationError

from framegen.spec import FrameSpec


def _valid(**overrides: object) -> FrameSpec:
    defaults: dict[str, object] = dict(
        frame_type="table",
        width_mm=1500.0,
        depth_mm=700.0,
        height_mm=900.0,
        profile_series="40-series",
        target_load_kg=100.0,
    )
    defaults.update(overrides)
    return FrameSpec.model_validate(defaults)


def test_valid_no_shelf() -> None:
    spec = _valid()
    assert spec.shelf_height_mm is None


def test_valid_with_shelf() -> None:
    spec = _valid(shelf_height_mm=300.0)
    assert spec.shelf_height_mm == 300.0


def test_negative_width_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(width_mm=-1.0)


def test_zero_width_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(width_mm=0.0)


def test_negative_depth_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(depth_mm=-1.0)


def test_negative_height_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(height_mm=-1.0)


def test_zero_load_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(target_load_kg=0.0)


def test_shelf_equal_to_height_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(shelf_height_mm=900.0, height_mm=900.0)


def test_shelf_above_height_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(shelf_height_mm=1000.0, height_mm=900.0)


def test_shelf_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        _valid(shelf_height_mm=0.0)
