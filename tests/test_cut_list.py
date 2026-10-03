from __future__ import annotations

from framegen.catalog import Profile
from framegen.generate.table import generate_table
from framegen.outputs.cut_list import build_cut_list
from framegen.spec import TableSpec


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


def test_no_shelf_row_counts_and_lengths() -> None:
    cl = build_cut_list(generate_table(_spec(), _profile()))
    by_length = {row.length_mm: row for row in cl.rows}

    assert by_length[900.0].qty == 4
    assert by_length[900.0].total_mm == 3600.0
    assert by_length[1420.0].qty == 2
    assert by_length[1420.0].total_mm == 2840.0
    assert by_length[620.0].qty == 2
    assert by_length[620.0].total_mm == 1240.0


def test_no_shelf_grand_total() -> None:
    cl = build_cut_list(generate_table(_spec(), _profile()))
    assert cl.total_mm == 7680.0


def test_with_shelf_row_counts_and_lengths() -> None:
    cl = build_cut_list(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    by_length = {row.length_mm: row for row in cl.rows}

    assert by_length[900.0].qty == 4
    assert by_length[900.0].total_mm == 3600.0
    assert by_length[1420.0].qty == 4   # 2 top + 2 shelf
    assert by_length[1420.0].total_mm == 5680.0
    assert by_length[620.0].qty == 4    # 2 top + 2 shelf
    assert by_length[620.0].total_mm == 2480.0


def test_with_shelf_grand_total() -> None:
    cl = build_cut_list(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    assert cl.total_mm == 11760.0


def test_grand_total_matches_row_sum() -> None:
    cl = build_cut_list(generate_table(_spec(shelf_height_mm=300.0), _profile()))
    assert cl.total_mm == sum(row.total_mm for row in cl.rows)
