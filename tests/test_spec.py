from __future__ import annotations

import pytest
from pydantic import ValidationError

from framegen.spec import (
    MAX_LEVEL_COUNT,
    MAX_LOAD_KG,
    MAX_WIDTH_MM,
    MIN_LEVEL_HEIGHT_MM,
    MIN_LEVEL_SPACING_MM,
    ShelfUnitSpec,
    TableSpec,
)

# ── TableSpec helpers ──────────────────────────────────────────────────────────

def _table(**overrides: object) -> TableSpec:
    defaults: dict[str, object] = dict(
        frame_type="table",
        width_mm=1500.0,
        depth_mm=700.0,
        height_mm=900.0,
        profile_series="40-series",
        target_load_kg=100.0,
    )
    defaults.update(overrides)
    return TableSpec.model_validate(defaults)


# ── TableSpec — existing tests (unchanged behaviour) ──────────────────────────

def test_valid_no_shelf() -> None:
    spec = _table()
    assert spec.shelf_height_mm is None


def test_valid_with_shelf() -> None:
    spec = _table(shelf_height_mm=300.0)
    assert spec.shelf_height_mm == 300.0


def test_negative_width_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(width_mm=-1.0)


def test_zero_width_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(width_mm=0.0)


def test_negative_depth_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(depth_mm=-1.0)


def test_negative_height_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(height_mm=-1.0)


def test_zero_load_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(target_load_kg=0.0)


def test_shelf_equal_to_height_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(shelf_height_mm=900.0, height_mm=900.0)


def test_shelf_above_height_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(shelf_height_mm=1000.0, height_mm=900.0)


def test_shelf_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        _table(shelf_height_mm=0.0)


class TestTableSanityLimits:
    def test_width_at_limit_accepted(self) -> None:
        spec = _table(width_mm=4000.0)
        assert spec.width_mm == 4000.0

    def test_width_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _table(width_mm=4001.0)

    def test_depth_at_limit_accepted(self) -> None:
        spec = _table(depth_mm=2000.0)
        assert spec.depth_mm == 2000.0

    def test_depth_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _table(depth_mm=2001.0)

    def test_height_at_limit_accepted(self) -> None:
        spec = _table(height_mm=2500.0)
        assert spec.height_mm == 2500.0

    def test_height_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _table(height_mm=2501.0)

    def test_load_at_limit_accepted(self) -> None:
        spec = _table(target_load_kg=2000.0)
        assert spec.target_load_kg == 2000.0

    def test_load_above_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _table(target_load_kg=2001.0)

    def test_error_message_content(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _table(width_mm=5000.0)
        msg = exc_info.value.errors()[0]["msg"]
        assert "width_mm" in msg
        assert "5000" in msg
        assert "4000" in msg
        assert "check the units" in msg


# ── ShelfUnitSpec helpers ──────────────────────────────────────────────────────

def _shelf(**overrides: object) -> ShelfUnitSpec:
    """900 × 400 × 1800, four evenly spaced levels, 30 kg/level."""
    defaults: dict[str, object] = dict(
        frame_type="shelf_unit",
        width_mm=900.0,
        depth_mm=400.0,
        height_mm=1800.0,
        profile_series="40-series",
        level_heights_mm=[450.0, 900.0, 1350.0, 1800.0],
        load_per_level_kg=30.0,
    )
    defaults.update(overrides)
    return ShelfUnitSpec.model_validate(defaults)


# ── ShelfUnitSpec — valid cases ────────────────────────────────────────────────

def test_shelf_unit_valid_basic() -> None:
    spec = _shelf()
    assert spec.frame_type == "shelf_unit"
    assert spec.level_heights_mm == [450.0, 900.0, 1350.0, 1800.0]
    assert spec.load_per_level_kg == 30.0
    assert spec.centre_legs is False


def test_shelf_unit_minimum_three_levels() -> None:
    spec = _shelf(
        height_mm=1200.0,
        level_heights_mm=[400.0, 800.0, 1200.0],
    )
    assert len(spec.level_heights_mm) == 3


def test_shelf_unit_maximum_ten_levels() -> None:
    h = 1800.0
    step = h / MAX_LEVEL_COUNT  # 180 mm — above MIN_LEVEL_SPACING_MM
    levels = [step * i for i in range(1, MAX_LEVEL_COUNT + 1)]
    spec = _shelf(height_mm=h, level_heights_mm=levels)
    assert len(spec.level_heights_mm) == MAX_LEVEL_COUNT


def test_shelf_unit_centre_legs_accepted() -> None:
    spec = _shelf(centre_legs=True)
    assert spec.centre_legs is True


# ── ShelfUnitSpec — level count limits ────────────────────────────────────────

def test_shelf_unit_two_levels_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 3"):
        _shelf(
            height_mm=600.0,
            level_heights_mm=[300.0, 600.0],
        )


def test_shelf_unit_one_level_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 3"):
        _shelf(
            height_mm=400.0,
            level_heights_mm=[400.0],
        )


def test_shelf_unit_eleven_levels_rejected() -> None:
    h = 2000.0
    # 11 levels with 181.8 mm spacing — spacing is fine but count exceeds MAX
    levels = [h * i / 11 for i in range(1, 12)]
    with pytest.raises(ValidationError, match=str(MAX_LEVEL_COUNT)):
        _shelf(height_mm=h, level_heights_mm=levels)


# ── ShelfUnitSpec — last entry must equal height_mm ───────────────────────────

def test_shelf_unit_last_entry_not_height_rejected() -> None:
    with pytest.raises(ValidationError, match="last entry"):
        _shelf(
            height_mm=1800.0,
            level_heights_mm=[450.0, 900.0, 1350.0, 1700.0],  # last ≠ 1800
        )


def test_shelf_unit_last_entry_above_height_rejected() -> None:
    with pytest.raises(ValidationError, match="last entry"):
        _shelf(
            height_mm=1800.0,
            level_heights_mm=[450.0, 900.0, 1350.0, 1900.0],
        )


# ── ShelfUnitSpec — ordering ───────────────────────────────────────────────────

def test_shelf_unit_duplicate_levels_rejected() -> None:
    with pytest.raises(ValidationError, match="strictly ascending"):
        _shelf(
            height_mm=1800.0,
            level_heights_mm=[450.0, 900.0, 900.0, 1800.0],
        )


def test_shelf_unit_descending_levels_rejected() -> None:
    with pytest.raises(ValidationError, match="strictly ascending"):
        _shelf(
            height_mm=1800.0,
            level_heights_mm=[900.0, 450.0, 300.0, 1800.0],
        )


# ── ShelfUnitSpec — minimum heights ───────────────────────────────────────────

def test_shelf_unit_first_level_at_minimum_accepted() -> None:
    # First level exactly at MIN_LEVEL_HEIGHT_MM (150 mm)
    spec = _shelf(
        height_mm=1800.0,
        level_heights_mm=[
            MIN_LEVEL_HEIGHT_MM,
            MIN_LEVEL_HEIGHT_MM + MIN_LEVEL_SPACING_MM,
            MIN_LEVEL_HEIGHT_MM + MIN_LEVEL_SPACING_MM * 2,
            1800.0,
        ],
    )
    assert spec.level_heights_mm[0] == MIN_LEVEL_HEIGHT_MM


def test_shelf_unit_first_level_below_minimum_rejected() -> None:
    with pytest.raises(ValidationError, match="minimum"):
        _shelf(
            height_mm=1800.0,
            level_heights_mm=[100.0, 600.0, 1200.0, 1800.0],
        )


def test_shelf_unit_spacing_at_minimum_accepted() -> None:
    # All gaps exactly MIN_LEVEL_SPACING_MM (150 mm)
    base = 300.0
    levels = [base, base + 150.0, base + 300.0, base + 450.0]
    spec = _shelf(height_mm=levels[-1], level_heights_mm=levels)
    assert spec.level_heights_mm[-1] == levels[-1]


def test_shelf_unit_spacing_below_minimum_rejected() -> None:
    with pytest.raises(ValidationError, match="minimum spacing"):
        _shelf(
            height_mm=1800.0,
            level_heights_mm=[300.0, 400.0, 900.0, 1800.0],  # gap 1→2 = 100 mm
        )


# ── ShelfUnitSpec — load and dimension limits ──────────────────────────────────

def test_shelf_unit_zero_load_rejected() -> None:
    with pytest.raises(ValidationError, match="load_per_level_kg must be positive"):
        _shelf(load_per_level_kg=0.0)


def test_shelf_unit_negative_load_rejected() -> None:
    with pytest.raises(ValidationError, match="load_per_level_kg must be positive"):
        _shelf(load_per_level_kg=-10.0)


def test_shelf_unit_load_at_limit_accepted() -> None:
    spec = _shelf(load_per_level_kg=MAX_LOAD_KG)
    assert spec.load_per_level_kg == MAX_LOAD_KG


def test_shelf_unit_load_above_limit_rejected() -> None:
    with pytest.raises(ValidationError, match="load_per_level_kg"):
        _shelf(load_per_level_kg=MAX_LOAD_KG + 1.0)


def test_shelf_unit_width_above_limit_rejected() -> None:
    with pytest.raises(ValidationError, match="width_mm"):
        _shelf(width_mm=MAX_WIDTH_MM + 1.0)


def test_shelf_unit_zero_width_rejected() -> None:
    with pytest.raises(ValidationError, match="width_mm must be positive"):
        _shelf(width_mm=0.0)
