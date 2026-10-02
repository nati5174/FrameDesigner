from __future__ import annotations

import pytest

from framegen.catalog import Profile
from framegen.generate.table import Bar, generate_table
from framegen.spec import FrameSpec

# W=1500, D=700, H=900, P=40 => rail lengths: 1500-80=1420, 700-80=620


def _profile(width: float = 40.0) -> Profile:
    return Profile(
        part_number="40-4040",
        series="40-series",
        profile_width_mm=width,
        source="80/20",
        source_url="https://8020.net/40-4040.html",
    )


def _spec(**overrides: object) -> FrameSpec:
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


def _by_role(bars: list[Bar]) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for bar in bars:
        result.setdefault(bar.role, []).append(bar.length_mm)
    return result


# ── Without shelf ─────────────────────────────────────────────────────────────

def test_no_shelf_total_bar_count() -> None:
    assert len(generate_table(_spec(), _profile())) == 8


def test_no_shelf_legs() -> None:
    by_role = _by_role(generate_table(_spec(), _profile()))
    assert sorted(by_role["leg"]) == [900.0, 900.0, 900.0, 900.0]


def test_no_shelf_top_rail_width() -> None:
    by_role = _by_role(generate_table(_spec(), _profile()))
    assert sorted(by_role["top_rail_width"]) == [1420.0, 1420.0]


def test_no_shelf_top_rail_depth() -> None:
    by_role = _by_role(generate_table(_spec(), _profile()))
    assert sorted(by_role["top_rail_depth"]) == [620.0, 620.0]


def test_no_shelf_total_material() -> None:
    bars = generate_table(_spec(), _profile())
    assert sum(b.length_mm for b in bars) == pytest.approx(7680.0)


# ── With shelf ────────────────────────────────────────────────────────────────

def test_with_shelf_total_bar_count() -> None:
    assert len(generate_table(_spec(shelf_height_mm=300.0), _profile())) == 12


def test_with_shelf_legs() -> None:
    by_role = _by_role(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    assert sorted(by_role["leg"]) == [900.0, 900.0, 900.0, 900.0]


def test_with_shelf_top_rail_width() -> None:
    by_role = _by_role(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    assert sorted(by_role["top_rail_width"]) == [1420.0, 1420.0]


def test_with_shelf_top_rail_depth() -> None:
    by_role = _by_role(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    assert sorted(by_role["top_rail_depth"]) == [620.0, 620.0]


def test_with_shelf_shelf_rail_width() -> None:
    by_role = _by_role(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    assert sorted(by_role["shelf_rail_width"]) == [1420.0, 1420.0]


def test_with_shelf_shelf_rail_depth() -> None:
    by_role = _by_role(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    assert sorted(by_role["shelf_rail_depth"]) == [620.0, 620.0]


def test_with_shelf_total_material() -> None:
    bars = generate_table(_spec(shelf_height_mm=300.0), _profile())
    assert sum(b.length_mm for b in bars) == pytest.approx(11760.0)


# ── Catalog-dependent validation ──────────────────────────────────────────────

def test_width_equal_to_2p_raises() -> None:
    with pytest.raises(ValueError, match="width_mm"):
        generate_table(_spec(width_mm=80.0), _profile())  # 80 == 2*P, not > 2P


def test_depth_equal_to_2p_raises() -> None:
    with pytest.raises(ValueError, match="depth_mm"):
        generate_table(_spec(depth_mm=80.0), _profile())


def test_height_below_p_raises() -> None:
    spec = FrameSpec.model_validate(
        dict(
            frame_type="table",
            width_mm=200.0,
            depth_mm=200.0,
            height_mm=30.0,
            profile_series="40-series",
            target_load_kg=10.0,
        )
    )
    with pytest.raises(ValueError, match="height_mm"):
        generate_table(spec, _profile())


def test_shelf_below_p_raises() -> None:
    # shelf_height_mm=39 < P=40; passes FrameSpec (39 < 900) but fails generate
    spec = FrameSpec.model_validate(
        dict(
            frame_type="table",
            width_mm=1500.0,
            depth_mm=700.0,
            height_mm=900.0,
            profile_series="40-series",
            target_load_kg=100.0,
            shelf_height_mm=39.0,
        )
    )
    with pytest.raises(ValueError, match="shelf_height_mm"):
        generate_table(spec, _profile())


def test_shelf_above_h_minus_p_raises() -> None:
    # shelf_height_mm=861 > H-P=860; passes FrameSpec (861 < 900) but fails generate
    spec = FrameSpec.model_validate(
        dict(
            frame_type="table",
            width_mm=1500.0,
            depth_mm=700.0,
            height_mm=900.0,
            profile_series="40-series",
            target_load_kg=100.0,
            shelf_height_mm=861.0,
        )
    )
    with pytest.raises(ValueError, match="shelf_height_mm"):
        generate_table(spec, _profile())
