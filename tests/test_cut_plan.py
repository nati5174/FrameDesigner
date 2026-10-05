"""Tests for src/framegen/outputs/cut_plan.py.

Each test calls _assert_valid(bars, result) which checks:
  - every piece from bars appears exactly once across stock_bars + does_not_fit
  - no stock bar exceeds stock_length_mm
  - offcut_mm and used_mm are internally consistent
"""
from __future__ import annotations

from collections import Counter

import pytest
from fastapi.testclient import TestClient

from framegen.api import app
from framegen.catalog import Profile
from framegen.generate import Bar, Point
from framegen.generate.table import generate_table
from framegen.outputs.cut_plan import (
    CutPlanResult,
    _ffd,
    plan_cuts,
)
from framegen.spec import TableSpec

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _profile() -> Profile:
    return Profile(
        part_number="40-4040",
        series="40-series",
        profile_width_mm=40.0,
        source="80/20",
        source_url="https://8020.net/40-4040.html",
    )


def _spec(**overrides: object) -> TableSpec:
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


def _make_bars(lengths: list[float], profile_id: str = "test-profile") -> list[Bar]:
    """Create synthetic bars with given lengths (all profile_id, role='leg')."""
    return [
        Bar(
            profile_id=profile_id,
            start=Point(0.0, 0.0, 0.0),
            end=Point(length, 0.0, 0.0),
            length_mm=length,
            role="leg",
        )
        for length in lengths
    ]


def _assert_valid(bars: list[Bar], result: CutPlanResult) -> None:
    """
    Validity invariants:
    1. Every piece from bars appears exactly once (stock_bars + does_not_fit).
    2. No stock bar used_mm exceeds stock_length_mm.
    3. offcut_mm == stock_length_mm - used_mm (within float tolerance).
    4. used_mm == sum(piece.length_mm + kerf_mm for piece in bar.pieces).
    """
    stock = result.stock_length_mm
    kerf = result.kerf_mm

    # Build expected piece counts by (profile_id, length_mm, label)
    expected: dict[str, Counter[tuple[float, str]]] = {}
    for bar in bars:
        pid = bar.profile_id
        if pid not in expected:
            expected[pid] = Counter()
        expected[pid][(bar.length_mm, bar.role)] += 1

    for profile in result.profiles:
        actual: Counter[tuple[float, str]] = Counter()

        for bar_plan in profile.stock_bars:
            # Consistency of used_mm
            computed_used = sum(p.length_mm + kerf for p in bar_plan.pieces)
            assert abs(computed_used - bar_plan.used_mm) < 1e-6, (
                f"used_mm mismatch: computed {computed_used}, stored {bar_plan.used_mm}"
            )
            # No overflow
            assert bar_plan.used_mm <= stock + 1e-6, (
                f"Stock bar used {bar_plan.used_mm} mm > stock {stock} mm"
            )
            # Offcut consistent
            assert abs(bar_plan.offcut_mm - (stock - bar_plan.used_mm)) < 1e-6, (
                f"offcut_mm {bar_plan.offcut_mm} inconsistent with "
                f"used_mm {bar_plan.used_mm}"
            )
            assert bar_plan.offcut_mm >= -1e-6, (
                f"Negative offcut: {bar_plan.offcut_mm}"
            )
            for piece in bar_plan.pieces:
                actual[(piece.length_mm, piece.label)] += 1

        for piece in profile.does_not_fit:
            assert piece.length_mm > stock, (
                f"does_not_fit piece {piece.length_mm} mm ≤ stock {stock} mm"
            )
            actual[(piece.length_mm, piece.label)] += 1

        expected_for_profile = expected.get(profile.profile_id, Counter())
        assert actual == expected_for_profile, (
            f"Piece counts mismatch for {profile.profile_id}: "
            f"expected {dict(expected_for_profile)}, got {dict(actual)}"
        )


# ── Reference table (no shelf) ────────────────────────────────────────────────
# Pieces: 2 × 1420, 4 × 900, 2 × 620.  Stock 3000, kerf 3.
# Expected: 3 bars (FFD optimal, lower bound = ceil(7704/3000) = 3).

def _ref_bars() -> list[Bar]:
    return generate_table(_spec(), _profile())


def test_reference_no_shelf_bar_count() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=3)
    assert result.profiles[0].total_stock_bars == 3


def test_reference_no_shelf_is_optimal() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=3)
    assert result.profiles[0].is_optimal is True


def test_reference_no_shelf_lower_bound() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=3)
    assert result.profiles[0].lower_bound_bars == 3


def test_reference_bar1_contents() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=3)
    bar1 = result.profiles[0].stock_bars[0]
    lengths = [p.length_mm for p in bar1.pieces]
    assert lengths == [1420.0, 1420.0]
    assert abs(bar1.used_mm - 2846.0) < 1e-6
    assert abs(bar1.offcut_mm - 154.0) < 1e-6


def test_reference_bar2_contents() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=3)
    bar2 = result.profiles[0].stock_bars[1]
    lengths = [p.length_mm for p in bar2.pieces]
    assert lengths == [900.0, 900.0, 900.0]
    assert abs(bar2.used_mm - 2709.0) < 1e-6
    assert abs(bar2.offcut_mm - 291.0) < 1e-6


def test_reference_bar3_contents() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=3)
    bar3 = result.profiles[0].stock_bars[2]
    lengths = [p.length_mm for p in bar3.pieces]
    assert sorted(lengths) == [620.0, 620.0, 900.0]
    assert abs(bar3.used_mm - 2149.0) < 1e-6
    assert abs(bar3.offcut_mm - 851.0) < 1e-6


def test_reference_no_shelf_waste_pct() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=3)
    # offcuts: 154 + 291 + 851 = 1296; 3 × 3000 = 9000; 1296/9000 × 100 = 14.4%
    assert abs(result.profiles[0].waste_pct - round(1296 / 9000 * 100, 4)) < 0.01


def test_reference_no_shelf_valid() -> None:
    bars = _ref_bars()
    _assert_valid(bars, plan_cuts(bars, stock_length_mm=3000, kerf_mm=3))


# ── Table with shelf: FFD gives 5, B&B finds 4 ────────────────────────────────
# Pieces: 4 × 1420, 4 × 900, 4 × 620.  Stock 3000, kerf 3.
# Lower bound = ceil(11796/3000) = 4.

def _shelf_bars() -> list[Bar]:
    return generate_table(_spec(shelf_height_mm=300.0), _profile())


def test_ffd_alone_gives_five_for_shelf() -> None:
    """Plain FFD gives 5 bars for the shelf table."""
    bars = _shelf_bars()
    sizes = sorted(
        [b.length_mm + 3.0 for b in bars],
        reverse=True,
    )
    assert len(_ffd(sizes, 3000.0)) == 5


def test_with_shelf_bar_count() -> None:
    result = plan_cuts(_shelf_bars(), stock_length_mm=3000, kerf_mm=3)
    assert result.profiles[0].total_stock_bars == 4


def test_with_shelf_lower_bound() -> None:
    result = plan_cuts(_shelf_bars(), stock_length_mm=3000, kerf_mm=3)
    assert result.profiles[0].lower_bound_bars == 4


def test_with_shelf_is_optimal() -> None:
    result = plan_cuts(_shelf_bars(), stock_length_mm=3000, kerf_mm=3)
    assert result.profiles[0].is_optimal is True


def test_with_shelf_bar_used_and_offcut() -> None:
    """Each bar should hold 1420 + 900 + 620 = used 2949, offcut 51."""
    result = plan_cuts(_shelf_bars(), stock_length_mm=3000, kerf_mm=3)
    for bar in result.profiles[0].stock_bars:
        assert abs(bar.used_mm - 2949.0) < 1e-6
        assert abs(bar.offcut_mm - 51.0) < 1e-6


def test_with_shelf_valid() -> None:
    bars = _shelf_bars()
    _assert_valid(bars, plan_cuts(bars, stock_length_mm=3000, kerf_mm=3))


# ── Piece longer than stock ───────────────────────────────────────────────────

def test_piece_longer_than_stock_goes_to_does_not_fit() -> None:
    bars = _make_bars([600.0])
    result = plan_cuts(bars, stock_length_mm=500, kerf_mm=3)
    profile = result.profiles[0]
    assert len(profile.does_not_fit) == 1
    assert profile.does_not_fit[0].length_mm == 600.0
    assert profile.total_stock_bars == 0


def test_piece_longer_than_stock_valid() -> None:
    bars = _make_bars([600.0])
    _assert_valid(bars, plan_cuts(bars, stock_length_mm=500, kerf_mm=3))


# ── Kerf = 0 ──────────────────────────────────────────────────────────────────
# Pieces: 2 × 1420, 4 × 900, 2 × 620.  Stock 3000, kerf 0.
# Bar 1: 1420+1420 = 2840, offcut 160.
# Lower bound = ceil(7680/3000) = 3.

def test_kerf_zero_bar_count() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=0)
    assert result.profiles[0].total_stock_bars == 3


def test_kerf_zero_bar1_used() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=0)
    bar1 = result.profiles[0].stock_bars[0]
    assert abs(bar1.used_mm - 2840.0) < 1e-6
    assert abs(bar1.offcut_mm - 160.0) < 1e-6


def test_kerf_zero_is_optimal() -> None:
    result = plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=0)
    assert result.profiles[0].is_optimal is True


def test_kerf_zero_valid() -> None:
    bars = _ref_bars()
    _assert_valid(bars, plan_cuts(bars, stock_length_mm=3000, kerf_mm=0))


# ── True minimum above lower bound ────────────────────────────────────────────
# Synthetic pieces: 4 x 600 mm + 2 x 500 mm, stock 1000, kerf 0.
# Total = 3400 mm.  Lower bound = ceil(3400/1000) = 4.
# 600+500 = 1100 > 1000; 600+600 = 1200 > 1000; only 500+500 = 1000 fits.
# Each 600 needs its own bin; the two 500s share one: 5 bins minimum.
# B&B exhausts and confirms 5. is_optimal = True.

def test_true_min_above_lower_bound_bar_count() -> None:
    bars = _make_bars([600.0, 600.0, 600.0, 600.0, 500.0, 500.0])
    result = plan_cuts(bars, stock_length_mm=1000, kerf_mm=0)
    profile = result.profiles[0]
    assert profile.lower_bound_bars == 4
    assert profile.total_stock_bars == 5


def test_true_min_above_lower_bound_is_optimal() -> None:
    """B&B proves 5 is the true minimum even though lower bound is 4."""
    bars = _make_bars([600.0, 600.0, 600.0, 600.0, 500.0, 500.0])
    result = plan_cuts(bars, stock_length_mm=1000, kerf_mm=0)
    assert result.profiles[0].is_optimal is True


def test_true_min_above_lower_bound_valid() -> None:
    bars = _make_bars([600.0, 600.0, 600.0, 600.0, 500.0, 500.0])
    _assert_valid(bars, plan_cuts(bars, stock_length_mm=1000, kerf_mm=0))


# ── Node limit: returns valid plan, is_optimal=False ─────────────────────────
# Force a tiny node limit so B&B stops early on the shelf table.
# FFD gives 5 bars; with node_limit=1 the search cannot find the 4-bar solution.

def test_node_limit_returns_valid_plan() -> None:
    bars = _shelf_bars()
    result = plan_cuts(bars, stock_length_mm=3000, kerf_mm=3, _node_limit=1)
    _assert_valid(bars, result)


def test_node_limit_is_not_optimal() -> None:
    bars = _shelf_bars()
    result = plan_cuts(bars, stock_length_mm=3000, kerf_mm=3, _node_limit=1)
    profile = result.profiles[0]
    # B&B did not exhaust and bar count > lower bound → not optimal
    assert profile.is_optimal is False


def test_node_limit_falls_back_to_ffd() -> None:
    bars = _shelf_bars()
    result = plan_cuts(bars, stock_length_mm=3000, kerf_mm=3, _node_limit=1)
    # With node limit of 1, the B&B cannot improve on FFD (5 bars)
    assert result.profiles[0].total_stock_bars == 5


# ── Input validation ──────────────────────────────────────────────────────────

def test_invalid_stock_too_small() -> None:
    with pytest.raises(ValueError, match="stock_length_mm"):
        plan_cuts(_ref_bars(), stock_length_mm=499, kerf_mm=3)


def test_invalid_stock_too_large() -> None:
    with pytest.raises(ValueError, match="stock_length_mm"):
        plan_cuts(_ref_bars(), stock_length_mm=8001, kerf_mm=3)


def test_invalid_kerf_negative() -> None:
    with pytest.raises(ValueError, match="kerf_mm"):
        plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=-1)


def test_invalid_kerf_too_large() -> None:
    with pytest.raises(ValueError, match="kerf_mm"):
        plan_cuts(_ref_bars(), stock_length_mm=3000, kerf_mm=11)


# ── API smoke test ────────────────────────────────────────────────────────────

def test_api_cut_plan_status() -> None:
    payload = {
        "spec": {
            "frame_type": "table",
            "width_mm": 1500,
            "depth_mm": 700,
            "height_mm": 900,
            "profile_series": "40-series",
            "target_load_kg": 100,
            "shelf_height_mm": None,
            "centre_legs": False,
            "level_heights_mm": None,
            "load_per_level_kg": None,
        },
        "stock_length_mm": 3000,
        "kerf_mm": 3,
    }
    resp = client.post("/cut-plan", json=payload)
    assert resp.status_code == 200


def test_api_cut_plan_profiles_non_empty() -> None:
    payload = {
        "spec": {
            "frame_type": "table",
            "width_mm": 1500,
            "depth_mm": 700,
            "height_mm": 900,
            "profile_series": "40-series",
            "target_load_kg": 100,
            "shelf_height_mm": None,
            "centre_legs": False,
            "level_heights_mm": None,
            "load_per_level_kg": None,
        },
        "stock_length_mm": 3000,
        "kerf_mm": 3,
    }
    resp = client.post("/cut-plan", json=payload)
    data = resp.json()
    assert len(data["profiles"]) > 0
    assert data["profiles"][0]["total_stock_bars"] == 3


def test_api_cut_plan_defaults() -> None:
    """stock_length_mm and kerf_mm have defaults."""
    payload = {
        "spec": {
            "frame_type": "table",
            "width_mm": 1500,
            "depth_mm": 700,
            "height_mm": 900,
            "profile_series": "40-series",
            "target_load_kg": 100,
            "shelf_height_mm": None,
            "centre_legs": False,
            "level_heights_mm": None,
            "load_per_level_kg": None,
        },
    }
    resp = client.post("/cut-plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["stock_length_mm"] == 3000.0
    assert data["kerf_mm"] == 3.0
