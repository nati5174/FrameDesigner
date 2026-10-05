"""
Tests for outputs/parts_list.py.

Reference frames are all 40-series; cost per joint = $7.59.

Test A: 1500×700×900 table, no shelf, no centre legs
  → 4 legs + 2 top_rail_width + 2 top_rail_depth = 8 bars, 4 rails, 8 joints
  → hardware_cost = $60.72

Test B: 1500×700×900 table with centre legs
  → 6 legs + 4 half-width rails + 2 depth rails = 12 bars, 6 rails, 12 joints
  → hardware_cost = $91.08

Test C: 900×400×1800 shelf unit, 4 levels at [450,900,1350,1800]
  → 4 legs + 16 level rails = 20 bars, 16 rails, 32 joints
  → hardware_cost = $242.88
"""
from __future__ import annotations

import pytest

from framegen.catalog import load_catalog
from framegen.generate.shelf_unit import generate_shelf_unit
from framegen.generate.table import generate_table
from framegen.outputs.parts_list import build_parts_list, count_joints
from framegen.spec import ShelfUnitSpec, TableSpec

_CATALOG = load_catalog()

_SPEC_A = TableSpec(
    frame_type="table",
    width_mm=1500,
    depth_mm=700,
    height_mm=900,
    profile_series="40-series",
    target_load_kg=100.0,
    centre_legs=False,
)

_SPEC_B = TableSpec(
    frame_type="table",
    width_mm=1500,
    depth_mm=700,
    height_mm=900,
    profile_series="40-series",
    target_load_kg=100.0,
    centre_legs=True,
)

_SPEC_C = ShelfUnitSpec(
    frame_type="shelf_unit",
    width_mm=900,
    depth_mm=400,
    height_mm=1800,
    profile_series="40-series",
    level_heights_mm=[450, 900, 1350, 1800],
    load_per_level_kg=30.0,
    centre_legs=False,
)


def _profile(series: str):
    return _CATALOG.profiles[series]


# ── count_joints ──────────────────────────────────────────────────────────────

def test_count_joints_table_basic():
    bars = generate_table(_SPEC_A, _profile("40-series"))
    assert count_joints(bars) == 8


def test_count_joints_table_centre_legs():
    bars = generate_table(_SPEC_B, _profile("40-series"))
    assert count_joints(bars) == 12


def test_count_joints_shelf_unit_4_levels():
    bars = generate_shelf_unit(_SPEC_C, _profile("40-series"))
    assert count_joints(bars) == 32


# ── build_parts_list — rows and totals ────────────────────────────────────────

def test_parts_list_table_basic():
    bars = generate_table(_SPEC_A, _profile("40-series"))
    result = build_parts_list(bars, _CATALOG.connectors, "40-series")
    assert result.hardware_priced is True
    assert len(result.rows) == 3

    bracket_row = result.rows[0]
    assert bracket_row.part_number == "40-4302"
    assert bracket_row.qty == 8
    assert bracket_row.line_total_usd == pytest.approx(42.48, abs=0.01)

    bolt_row = result.rows[1]
    assert bolt_row.part_number == "13-8316"
    assert bolt_row.qty == 16
    assert bolt_row.line_total_usd == pytest.approx(9.76, abs=0.01)

    tnut_row = result.rows[2]
    assert tnut_row.part_number == "3838"
    assert tnut_row.qty == 16
    assert tnut_row.line_total_usd == pytest.approx(8.48, abs=0.01)

    assert result.hardware_cost_usd == pytest.approx(60.72, abs=0.01)


def test_parts_list_table_centre_legs():
    bars = generate_table(_SPEC_B, _profile("40-series"))
    result = build_parts_list(bars, _CATALOG.connectors, "40-series")
    assert result.hardware_priced is True
    assert result.hardware_cost_usd == pytest.approx(91.08, abs=0.01)


def test_parts_list_shelf_4_levels():
    bars = generate_shelf_unit(_SPEC_C, _profile("40-series"))
    result = build_parts_list(bars, _CATALOG.connectors, "40-series")
    assert result.hardware_priced is True
    assert result.hardware_cost_usd == pytest.approx(242.88, abs=0.01)


def test_parts_list_missing_hardware_none():
    bars = generate_table(_SPEC_A, _profile("40-series"))
    result = build_parts_list(bars, None, "40-series")
    assert result.hardware_priced is False
    assert result.hardware_cost_usd is None
    assert result.rows == ()


def test_parts_list_missing_hardware_unknown_series():
    bars = generate_table(_SPEC_A, _profile("40-series"))
    result = build_parts_list(bars, _CATALOG.connectors, "unknown-series")
    assert result.hardware_priced is False
    assert result.hardware_cost_usd is None
    assert result.rows == ()


def test_parts_list_line_totals_sum_to_hardware_total():
    for spec, series in [
        (_SPEC_A, "40-series"),
        (_SPEC_B, "40-series"),
        (_SPEC_C, "40-series"),
    ]:
        if isinstance(spec, ShelfUnitSpec):
            bars = generate_shelf_unit(spec, _profile(series))
        else:
            bars = generate_table(spec, _profile(series))
        result = build_parts_list(bars, _CATALOG.connectors, series)
        assert result.hardware_priced is True
        assert sum(r.line_total_usd for r in result.rows) == pytest.approx(
            result.hardware_cost_usd, abs=0.01  # type: ignore[arg-type]
        )


# ── hardware weight ───────────────────────────────────────────────────────────

def test_hardware_weight_table_basic():
    """Hardware weight is returned when all parts have weight_kg."""
    bars = generate_table(_SPEC_A, _profile("40-series"))
    result = build_parts_list(bars, _CATALOG.connectors, "40-series")
    assert result.hardware_priced is True
    assert result.hardware_weight_kg is not None
    assert result.hardware_weight_kg > 0
