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


# ── Sanity limits ─────────────────────────────────────────────────────────────

class TestSanityLimits:
    def test_width_at_limit_accepted(self) -> None:
        spec = _valid(width_mm=4000.0)
        assert spec.width_mm == 4000.0

    def test_width_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid(width_mm=4001.0)

    def test_depth_at_limit_accepted(self) -> None:
        spec = _valid(depth_mm=2000.0)
        assert spec.depth_mm == 2000.0

    def test_depth_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid(depth_mm=2001.0)

    def test_height_at_limit_accepted(self) -> None:
        spec = _valid(height_mm=2500.0)
        assert spec.height_mm == 2500.0

    def test_height_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid(height_mm=2501.0)

    def test_load_at_limit_accepted(self) -> None:
        spec = _valid(target_load_kg=2000.0)
        assert spec.target_load_kg == 2000.0

    def test_load_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid(target_load_kg=2001.0)

    def test_error_message_content(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _valid(width_mm=5000.0)
        msg = exc_info.value.errors()[0]["msg"]
        assert "width_mm" in msg
        assert "5000" in msg
        assert "4000" in msg
        assert "check the units" in msg
