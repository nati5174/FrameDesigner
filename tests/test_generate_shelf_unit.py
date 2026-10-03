from __future__ import annotations

import pytest

from framegen.catalog import Profile
from framegen.checks import check_collision, check_connectivity
from framegen.generate.shelf_unit import generate_shelf_unit
from framegen.generate.table import Bar
from framegen.spec import ShelfUnitSpec

# ── Fixtures ──────────────────────────────────────────────────────────────────
# Worked example from the plan: 900 × 400 × 1800 mm, 4 levels, 40-series.
#   P = 40  →  rail lengths: W − 2P = 820,  D − 2P = 320
#   Levels at 450, 900, 1350, 1800 mm (evenly spaced).
#   Expected: 4 legs × 1800 + 8 width rails × 820 + 8 depth rails × 320 = 20 bars
#   Total material: 4×1800 + 8×820 + 8×320 = 7200 + 6560 + 2560 = 16 320 mm


def _profile() -> Profile:
    return Profile(
        part_number="40-4040",
        series="40-series",
        profile_width_mm=40.0,
        source="80/20",
        source_url="https://8020.net/40-4040.html",
    )


def _spec(**overrides: object) -> ShelfUnitSpec:
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


def _by_role(bars: list[Bar]) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for bar in bars:
        result.setdefault(bar.role, []).append(bar.length_mm)
    return result


# ── Bar counts and lengths ─────────────────────────────────────────────────────

def test_total_bar_count() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    assert len(bars) == 20


def test_legs_count_and_length() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    legs = [b for b in bars if b.role == "leg"]
    assert len(legs) == 4
    assert all(b.length_mm == pytest.approx(1800.0) for b in legs)


def test_width_rails_count_and_length() -> None:
    # 2 per level × 4 levels = 8; each W − 2P = 900 − 80 = 820 mm
    bars = generate_shelf_unit(_spec(), _profile())
    width_rails = [b for b in bars if b.role == "level_rail_width"]
    assert len(width_rails) == 8
    assert all(b.length_mm == pytest.approx(820.0) for b in width_rails)


def test_depth_rails_count_and_length() -> None:
    # 2 per level × 4 levels = 8; each D − 2P = 400 − 80 = 320 mm
    bars = generate_shelf_unit(_spec(), _profile())
    depth_rails = [b for b in bars if b.role == "level_rail_depth"]
    assert len(depth_rails) == 8
    assert all(b.length_mm == pytest.approx(320.0) for b in depth_rails)


def test_total_material_mm() -> None:
    # 4×1800 + 8×820 + 8×320 = 16 320 mm
    bars = generate_shelf_unit(_spec(), _profile())
    total = sum(b.length_mm for b in bars)
    assert total == pytest.approx(16320.0)


# ── level_index assignment ─────────────────────────────────────────────────────

def test_legs_have_no_level_index() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    legs = [b for b in bars if b.role == "leg"]
    assert all(b.level_index is None for b in legs)


def test_rails_carry_correct_level_index() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    for expected_idx in range(4):
        rails_at_level = [
            b for b in bars
            if b.role in ("level_rail_width", "level_rail_depth")
            and b.level_index == expected_idx
        ]
        # 2 width + 2 depth = 4 rails per level
        assert len(rails_at_level) == 4, (
            f"expected 4 rails at level {expected_idx}, got {len(rails_at_level)}"
        )


def test_all_level_indices_present() -> None:
    bars = generate_shelf_unit(_spec(), _profile())
    rail_indices = {
        b.level_index
        for b in bars
        if b.role in ("level_rail_width", "level_rail_depth")
    }
    assert rail_indices == {0, 1, 2, 3}


# ── Structural checks ─────────────────────────────────────────────────────────

def test_no_collision() -> None:
    profile = _profile()
    bars = generate_shelf_unit(_spec(), profile)
    result = check_collision(bars, profile.profile_width_mm)
    assert result.passed is True
    assert result.colliding_pairs == []


def test_connectivity_passes() -> None:
    profile = _profile()
    bars = generate_shelf_unit(_spec(), profile)
    result = check_connectivity(bars, profile.profile_width_mm)
    assert result.passed is True
    assert result.disconnected_bar_indices == []


# ── Centre legs ───────────────────────────────────────────────────────────────
# W=900, P=40 → W > 3P=120; half-rail length = (W − 3P)/2 = (900−120)/2 = 390 mm

def test_centre_legs_total_bar_count() -> None:
    # 4 corner legs + 2 centre legs + 4 levels × (4 width half-rails + 2 depth) = 30
    bars = generate_shelf_unit(_spec(centre_legs=True), _profile())
    assert len(bars) == 30


def test_centre_legs_leg_count() -> None:
    bars = generate_shelf_unit(_spec(centre_legs=True), _profile())
    legs = [b for b in bars if b.role in ("leg", "centre_leg")]
    assert len(legs) == 6
    assert all(b.length_mm == pytest.approx(1800.0) for b in legs)


def test_centre_legs_width_half_rail_length() -> None:
    # (900 − 3×40) / 2 = 390 mm
    bars = generate_shelf_unit(_spec(centre_legs=True), _profile())
    width_rails = [b for b in bars if b.role == "level_rail_width"]
    assert len(width_rails) == 16  # 4 per level × 4 levels
    assert all(b.length_mm == pytest.approx(390.0) for b in width_rails)


def test_centre_legs_depth_rail_length() -> None:
    bars = generate_shelf_unit(_spec(centre_legs=True), _profile())
    depth_rails = [b for b in bars if b.role == "level_rail_depth"]
    assert len(depth_rails) == 8
    assert all(b.length_mm == pytest.approx(320.0) for b in depth_rails)


def test_centre_legs_no_collision() -> None:
    profile = _profile()
    bars = generate_shelf_unit(_spec(centre_legs=True), profile)
    assert check_collision(bars, profile.profile_width_mm).passed is True


def test_centre_legs_connectivity_passes() -> None:
    profile = _profile()
    bars = generate_shelf_unit(_spec(centre_legs=True), profile)
    assert check_connectivity(bars, profile.profile_width_mm).passed is True


# ── Geometry guard ────────────────────────────────────────────────────────────

def test_width_too_small_raises() -> None:
    # W = 2P = 80: must exceed, not equal
    with pytest.raises(ValueError, match="width_mm"):
        generate_shelf_unit(
            _spec(width_mm=80.0),
            _profile(),
        )


def test_centre_legs_width_too_small_raises() -> None:
    # W = 3P = 120: centre_legs requires W > 3P
    with pytest.raises(ValueError, match="centre_legs"):
        generate_shelf_unit(
            _spec(width_mm=120.0, centre_legs=True),
            _profile(),
        )
