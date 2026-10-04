"""Tests for the rule-based edit parser."""
from __future__ import annotations

import pytest

from framegen.parser.edit_rule import (
    Operation,
    parse_edit,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ops(text: str) -> list[Operation]:
    r = parse_edit(text)
    assert r.outcome == "operations", (
        f"Expected operations, got {r.outcome!r} for {text!r}"
    )
    return r.operations


def _op1(text: str) -> Operation:
    ops = _ops(text)
    assert len(ops) == 1, f"Expected 1 op, got {len(ops)} for {text!r}"
    return ops[0]


# ── New-design detection ──────────────────────────────────────────────────────

class TestNewDesign:
    def test_start_over(self) -> None:
        assert parse_edit("start over").outcome == "new_design"

    def test_start_again(self) -> None:
        assert parse_edit("start again").outcome == "new_design"

    def test_from_scratch(self) -> None:
        assert parse_edit("from scratch, make a new frame").outcome == "new_design"

    def test_instead_build(self) -> None:
        assert parse_edit("instead build something else").outcome == "new_design"

    def test_new_design_keyword(self) -> None:
        assert parse_edit("new design please").outcome == "new_design"

    def test_frame_type_plus_dims_is_new_design(self) -> None:
        # Frame type + W×D → new design
        assert parse_edit("table 1500 x 700 mm").outcome == "new_design"

    def test_frame_type_without_both_dims_is_not_new_design(self) -> None:
        # "make it a table" has no dimensions → falls through to not_matched
        r = parse_edit("make it a table")
        assert r.outcome in ("not_matched", "operations")

    def test_shelf_unit_plus_dims(self) -> None:
        assert parse_edit("shelf unit 1200 x 500 mm").outcome == "new_design"


# ── Height ────────────────────────────────────────────────────────────────────

class TestHeight:
    def test_add_taller(self) -> None:
        op = _op1("make it 200 mm taller")
        assert op.field == "height_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(200.0)

    def test_add_taller_no_make_it(self) -> None:
        op = _op1("200 mm taller")
        assert op.field == "height_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(200.0)

    def test_taller_by(self) -> None:
        op = _op1("taller by 300 mm")
        assert op.field == "height_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(300.0)

    def test_add_shorter(self) -> None:
        op = _op1("100 mm shorter")
        assert op.field == "height_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(-100.0)

    def test_shorter_by(self) -> None:
        op = _op1("shorter by 50 mm")
        assert op.op == "add"
        assert op.value == pytest.approx(-50.0)

    def test_set_tall(self) -> None:
        op = _op1("make it 1100 mm tall")
        assert op.field == "height_mm"
        assert op.op == "set"
        assert op.value == pytest.approx(1100.0)

    def test_set_tall_no_make_it(self) -> None:
        op = _op1("1100 mm tall")
        assert op.op == "set"
        assert op.value == pytest.approx(1100.0)

    def test_set_high(self) -> None:
        op = _op1("900 mm high")
        assert op.field == "height_mm"
        assert op.op == "set"

    def test_height_keyword(self) -> None:
        op = _op1("height 900 mm")
        assert op.field == "height_mm"
        assert op.op == "set"
        assert op.value == pytest.approx(900.0)

    def test_height_to(self) -> None:
        op = _op1("height to 1200 mm")
        assert op.op == "set"
        assert op.value == pytest.approx(1200.0)

    def test_height_cm_conversion(self) -> None:
        op = _op1("taller by 20 cm")
        assert op.value == pytest.approx(200.0)

    def test_height_m_conversion(self) -> None:
        op = _op1("make it 1.2 m tall")
        assert op.value == pytest.approx(1200.0)

    def test_taller_not_tall(self) -> None:
        # "taller" must not set, must add
        op = _op1("200 mm taller")
        assert op.op == "add"


# ── Width ─────────────────────────────────────────────────────────────────────

class TestWidth:
    def test_add_wider(self) -> None:
        op = _op1("200 mm wider")
        assert op.field == "width_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(200.0)

    def test_wider_by(self) -> None:
        op = _op1("wider by 100 mm")
        assert op.op == "add"
        assert op.value == pytest.approx(100.0)

    def test_add_narrower(self) -> None:
        op = _op1("300 mm narrower")
        assert op.op == "add"
        assert op.value == pytest.approx(-300.0)

    def test_narrower_by(self) -> None:
        op = _op1("narrower by 200 mm")
        assert op.op == "add"
        assert op.value == pytest.approx(-200.0)

    def test_set_wide(self) -> None:
        op = _op1("1600 mm wide")
        assert op.field == "width_mm"
        assert op.op == "set"
        assert op.value == pytest.approx(1600.0)

    def test_set_wide_make_it(self) -> None:
        op = _op1("make it 1600 mm wide")
        assert op.op == "set"

    def test_width_keyword(self) -> None:
        op = _op1("width 1800 mm")
        assert op.field == "width_mm"
        assert op.op == "set"
        assert op.value == pytest.approx(1800.0)

    def test_width_to(self) -> None:
        op = _op1("width to 2000 mm")
        assert op.op == "set"
        assert op.value == pytest.approx(2000.0)


# ── Depth ─────────────────────────────────────────────────────────────────────

class TestDepth:
    def test_add_deeper(self) -> None:
        op = _op1("100 mm deeper")
        assert op.field == "depth_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(100.0)

    def test_deeper_by(self) -> None:
        op = _op1("deeper by 150 mm")
        assert op.op == "add"
        assert op.value == pytest.approx(150.0)

    def test_add_shallower(self) -> None:
        op = _op1("100 mm shallower")
        assert op.field == "depth_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(-100.0)

    def test_shallower_by(self) -> None:
        op = _op1("shallower by 50 mm")
        assert op.op == "add"
        assert op.value == pytest.approx(-50.0)

    def test_set_deep(self) -> None:
        op = _op1("800 mm deep")
        assert op.field == "depth_mm"
        assert op.op == "set"
        assert op.value == pytest.approx(800.0)

    def test_depth_keyword(self) -> None:
        op = _op1("depth 600 mm")
        assert op.field == "depth_mm"
        assert op.op == "set"

    def test_depth_to(self) -> None:
        op = _op1("depth to 750 mm")
        assert op.op == "set"
        assert op.value == pytest.approx(750.0)


# ── Load ──────────────────────────────────────────────────────────────────────

class TestLoad:
    def test_holds_n_kg(self) -> None:
        op = _op1("holds 150 kg")
        assert op.field == "target_load_kg"
        assert op.op == "set"
        assert op.value == pytest.approx(150.0)

    def test_can_it_hold(self) -> None:
        op = _op1("can it hold 150 kg")
        assert op.field == "target_load_kg"
        assert op.op == "set"
        assert op.value == pytest.approx(150.0)

    def test_load_keyword(self) -> None:
        op = _op1("load 200 kg")
        assert op.field == "target_load_kg"
        assert op.op == "set"

    def test_change_load_to(self) -> None:
        op = _op1("change the load to 250 kg")
        assert op.op == "set"
        assert op.value == pytest.approx(250.0)

    def test_n_kg_load(self) -> None:
        op = _op1("300 kg load")
        assert op.field == "target_load_kg"
        assert op.value == pytest.approx(300.0)

    def test_target_load(self) -> None:
        op = _op1("target load 120 kg")
        assert op.field == "target_load_kg"


# ── Load per level ────────────────────────────────────────────────────────────

class TestLoadPerLevel:
    def test_n_kg_per_level(self) -> None:
        op = _op1("50 kg per level")
        assert op.field == "load_per_level_kg"
        assert op.op == "set"
        assert op.value == pytest.approx(50.0)

    def test_load_per_level_to(self) -> None:
        op = _op1("load per level to 40 kg")
        assert op.field == "load_per_level_kg"
        assert op.value == pytest.approx(40.0)

    def test_per_shelf(self) -> None:
        op = _op1("30 kg per shelf")
        assert op.field == "load_per_level_kg"


# ── Shelf ─────────────────────────────────────────────────────────────────────

class TestShelf:
    def test_add_shelf_default(self) -> None:
        op = _op1("add a shelf")
        assert op.field == "shelf_height_mm"
        assert op.op == "set"
        assert op.value == pytest.approx(300.0)

    def test_add_shelf_at(self) -> None:
        op = _op1("add a shelf at 400 mm")
        assert op.field == "shelf_height_mm"
        assert op.op == "set"
        assert op.value == pytest.approx(400.0)

    def test_remove_shelf(self) -> None:
        op = _op1("remove the shelf")
        assert op.field == "shelf_height_mm"
        assert op.op == "set"
        assert op.value is None

    def test_no_shelf(self) -> None:
        op = _op1("no shelf")
        assert op.value is None

    def test_raise_shelf_by(self) -> None:
        op = _op1("raise the shelf by 100 mm")
        assert op.field == "shelf_height_mm"
        assert op.op == "add"
        assert op.value == pytest.approx(100.0)

    def test_raise_shelf_to(self) -> None:
        op = _op1("raise the shelf to 500 mm")
        assert op.op == "set"
        assert op.value == pytest.approx(500.0)

    def test_lower_shelf_by(self) -> None:
        op = _op1("lower the shelf by 50 mm")
        assert op.op == "add"
        assert op.value == pytest.approx(-50.0)

    def test_lower_shelf_to(self) -> None:
        op = _op1("lower the shelf to 250 mm")
        assert op.op == "set"
        assert op.value == pytest.approx(250.0)

    def test_shelf_at(self) -> None:
        op = _op1("shelf at 350 mm")
        assert op.op == "set"
        assert op.value == pytest.approx(350.0)


# ── Centre legs ───────────────────────────────────────────────────────────────

class TestCentreLegs:
    def test_add_centre_legs(self) -> None:
        op = _op1("add centre legs")
        assert op.field == "centre_legs"
        assert op.op == "set"
        assert op.value is True

    def test_center_legs_us(self) -> None:
        op = _op1("center legs")
        assert op.value is True

    def test_middle_legs(self) -> None:
        op = _op1("middle legs")
        assert op.value is True

    def test_middle_support(self) -> None:
        op = _op1("middle support")
        assert op.value is True

    def test_remove_centre_legs(self) -> None:
        op = _op1("remove centre legs")
        assert op.field == "centre_legs"
        assert op.value is False

    def test_no_centre_legs(self) -> None:
        op = _op1("no centre legs")
        assert op.value is False

    def test_no_middle_support(self) -> None:
        op = _op1("no middle support")
        assert op.value is False


# ── Shelf unit levels ─────────────────────────────────────────────────────────

class TestLevels:
    def test_add_level_at(self) -> None:
        op = _op1("add a level at 600 mm")
        assert op.field == "level_heights_mm"
        assert op.op == "add_level"
        assert op.value == pytest.approx(600.0)

    def test_add_new_level_at(self) -> None:
        op = _op1("add a new level at 900 mm")
        assert op.op == "add_level"
        assert op.value == pytest.approx(900.0)

    def test_remove_level(self) -> None:
        op = _op1("remove a level")
        assert op.field == "level_heights_mm"
        assert op.op == "remove_level"
        assert op.value is None

    def test_remove_top_level(self) -> None:
        op = _op1("remove the top level")
        assert op.op == "remove_level"

    def test_set_level_count(self) -> None:
        op = _op1("4 levels")
        assert op.field == "level_heights_mm"
        assert op.op == "set_level_count"
        assert op.value == pytest.approx(4.0)

    def test_set_to_n_levels(self) -> None:
        op = _op1("set to 5 levels")
        assert op.op == "set_level_count"
        assert op.value == pytest.approx(5.0)


# ── Block pattern ─────────────────────────────────────────────────────────────

class TestBlock:
    def test_w_x_d(self) -> None:
        ops = _ops("1600 x 800 mm")
        fields = {o.field for o in ops}
        assert fields == {"width_mm", "depth_mm"}
        w_op = next(o for o in ops if o.field == "width_mm")
        d_op = next(o for o in ops if o.field == "depth_mm")
        assert w_op.value == pytest.approx(1600.0)
        assert d_op.value == pytest.approx(800.0)

    def test_w_x_d_x_h(self) -> None:
        ops = _ops("1600 x 800 x 1000 mm")
        fields = {o.field for o in ops}
        assert fields == {"width_mm", "depth_mm", "height_mm"}

    def test_block_unitless_small_returns_not_matched(self) -> None:
        # bare numbers < 100 are ambiguous
        r = parse_edit("15 x 7")
        assert r.outcome == "not_matched"

    def test_block_no_unit_large(self) -> None:
        # bare numbers ≥ 100 are treated as mm
        ops = _ops("1500 x 700")
        assert len(ops) == 2


# ── Compound edits ────────────────────────────────────────────────────────────

class TestCompound:
    def test_height_and_load(self) -> None:
        ops = _ops("make it 200 mm taller and change the load to 150 kg")
        fields = {o.field for o in ops}
        assert "height_mm" in fields
        assert "target_load_kg" in fields

    def test_height_and_width(self) -> None:
        ops = _ops("200 mm taller and 100 mm wider")
        fields = {o.field for o in ops}
        assert "height_mm" in fields
        assert "width_mm" in fields

    def test_shelf_and_centre_legs(self) -> None:
        ops = _ops("add a shelf and add centre legs")
        fields = {o.field for o in ops}
        assert "shelf_height_mm" in fields
        assert "centre_legs" in fields


# ── Not matched ───────────────────────────────────────────────────────────────

class TestNotMatched:
    def test_random_text(self) -> None:
        assert parse_edit("hello there").outcome == "not_matched"

    def test_question_without_number(self) -> None:
        assert parse_edit("what bolts do I need").outcome == "not_matched"

    def test_add_level_without_height(self) -> None:
        # "add a level" without a specific height → not matched
        assert parse_edit("add a level").outcome == "not_matched"
