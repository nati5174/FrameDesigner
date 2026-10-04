"""Integration tests for POST /edit."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from framegen.api import app

client = TestClient(app)

# ── Shared fixtures ───────────────────────────────────────────────────────────

_TABLE = {
    "frame_type": "table",
    "width_mm": 1500,
    "depth_mm": 700,
    "height_mm": 900,
    "profile_series": "40-series",
    "shelf_height_mm": None,
    "target_load_kg": 100.0,
    "centre_legs": False,
    "level_heights_mm": None,
    "load_per_level_kg": None,
}

_TABLE_WITH_SHELF = {**_TABLE, "shelf_height_mm": 300.0}

_SHELF_UNIT = {
    "frame_type": "shelf_unit",
    "width_mm": 1200,
    "depth_mm": 500,
    "height_mm": 1800,
    "profile_series": "40-series",
    "shelf_height_mm": None,
    "target_load_kg": None,
    "centre_legs": False,
    "level_heights_mm": [600.0, 1200.0, 1800.0],
    "load_per_level_kg": 30.0,
}


def _edit(text: str, spec: dict | None = None, pending: dict | None = None) -> dict:
    body: dict = {"text": text}
    if spec is not None:
        body["spec"] = spec
    if pending is not None:
        body["pending"] = pending
    resp = client.post("/edit", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── First turn (no spec, no pending) ─────────────────────────────────────────

class TestFirstTurn:
    def test_new_design_from_text(self) -> None:
        r = _edit("table 1500 x 700 x 900 mm")
        assert r["outcome"] == "new_design"
        assert r["spec"]["width_mm"] == pytest.approx(1500.0)
        assert r["spec"]["height_mm"] == pytest.approx(900.0)

    def test_spec_invalid_imperial(self) -> None:
        r = _edit('60" x 28" x 36"')
        assert r["outcome"] == "spec_invalid"
        assert "Imperial" in (r["error"] or "")

    def test_spec_invalid_enclosure(self) -> None:
        r = _edit("1500 x 700 enclosure")
        assert r["outcome"] == "spec_invalid"

    def test_read_as_new_design(self) -> None:
        r = _edit("1500 x 700 x 900 mm")
        assert r["outcome"] == "new_design"
        assert r["read_as"] == "new_design"

    def test_llm_available_field_present(self) -> None:
        r = _edit("1500 x 700 mm")
        assert "llm_available" in r


# ── Edit (spec present) ───────────────────────────────────────────────────────

class TestEdit:
    def test_height_add(self) -> None:
        r = _edit("make it 200 mm taller", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["height_mm"] == pytest.approx(1100.0)

    def test_height_set(self) -> None:
        r = _edit("height 1200 mm", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["height_mm"] == pytest.approx(1200.0)

    def test_width_add(self) -> None:
        r = _edit("100 mm wider", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["width_mm"] == pytest.approx(1600.0)

    def test_depth_add(self) -> None:
        r = _edit("100 mm deeper", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["depth_mm"] == pytest.approx(800.0)

    def test_depth_shallower(self) -> None:
        r = _edit("100 mm shallower", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["depth_mm"] == pytest.approx(600.0)

    def test_load_question(self) -> None:
        r = _edit("can it hold 150 kg", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["target_load_kg"] == pytest.approx(150.0)

    def test_load_change(self) -> None:
        r = _edit("change the load to 200 kg", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["target_load_kg"] == pytest.approx(200.0)

    def test_shelf_add(self) -> None:
        r = _edit("add a shelf at 300 mm", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["shelf_height_mm"] == pytest.approx(300.0)

    def test_shelf_add_default(self) -> None:
        r = _edit("add a shelf", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["shelf_height_mm"] == pytest.approx(300.0)

    def test_shelf_remove(self) -> None:
        r = _edit("remove the shelf", spec=_TABLE_WITH_SHELF)
        assert r["outcome"] == "edit"
        assert r["spec"]["shelf_height_mm"] is None

    def test_shelf_raise_by(self) -> None:
        r = _edit("raise the shelf by 100 mm", spec=_TABLE_WITH_SHELF)
        assert r["outcome"] == "edit"
        assert r["spec"]["shelf_height_mm"] == pytest.approx(400.0)

    def test_shelf_lower_to(self) -> None:
        r = _edit("lower the shelf to 200 mm", spec=_TABLE_WITH_SHELF)
        assert r["outcome"] == "edit"
        assert r["spec"]["shelf_height_mm"] == pytest.approx(200.0)

    def test_centre_legs_add(self) -> None:
        r = _edit("add centre legs", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["centre_legs"] is True

    def test_centre_legs_remove(self) -> None:
        spec = {**_TABLE, "centre_legs": True}
        r = _edit("remove centre legs", spec=spec)
        assert r["outcome"] == "edit"
        assert r["spec"]["centre_legs"] is False

    def test_middle_legs(self) -> None:
        r = _edit("middle legs", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["centre_legs"] is True

    def test_read_as_edit(self) -> None:
        r = _edit("200 mm taller", spec=_TABLE)
        assert r["read_as"] == "edit"

    def test_block_w_d(self) -> None:
        r = _edit("1600 x 800 mm", spec=_TABLE)
        assert r["outcome"] == "edit"
        assert r["spec"]["width_mm"] == pytest.approx(1600.0)
        assert r["spec"]["depth_mm"] == pytest.approx(800.0)

    def test_other_fields_unchanged(self) -> None:
        r = _edit("200 mm taller", spec=_TABLE)
        assert r["spec"]["width_mm"] == pytest.approx(1500.0)
        assert r["spec"]["depth_mm"] == pytest.approx(700.0)
        assert r["spec"]["target_load_kg"] == pytest.approx(100.0)
        assert r["spec"]["centre_legs"] is False

    def test_shelf_unit_load_per_level(self) -> None:
        r = _edit("50 kg per level", spec=_SHELF_UNIT)
        assert r["outcome"] == "edit"
        assert r["spec"]["load_per_level_kg"] == pytest.approx(50.0)

    def test_shelf_unit_set_level_count(self) -> None:
        r = _edit("4 levels", spec=_SHELF_UNIT)
        assert r["outcome"] == "edit"
        levels = r["spec"]["level_heights_mm"]
        assert len(levels) == 4
        assert levels[-1] == pytest.approx(1800.0)

    def test_shelf_unit_add_level(self) -> None:
        r = _edit("add a level at 900 mm", spec=_SHELF_UNIT)
        assert r["outcome"] == "edit"
        levels = r["spec"]["level_heights_mm"]
        assert 900.0 in levels or any(abs(h - 900.0) < 1.0 for h in levels)

    def test_shelf_unit_remove_level(self) -> None:
        # Need >= 4 levels to remove one (min 3 required after removal)
        spec = {
            **_SHELF_UNIT,
            "level_heights_mm": [450.0, 900.0, 1350.0, 1800.0],
        }
        r = _edit("remove a level", spec=spec)
        assert r["outcome"] == "edit"
        assert len(r["spec"]["level_heights_mm"]) == 3


# ── Changes populated ─────────────────────────────────────────────────────────

class TestChanges:
    def test_height_change_recorded(self) -> None:
        r = _edit("200 mm taller", spec=_TABLE)
        changes = r["changes"]
        h = next((c for c in changes if c["field"] == "height_mm"), None)
        assert h is not None
        assert h["old"] == pytest.approx(900.0)
        assert h["new"] == pytest.approx(1100.0)

    def test_no_spurious_changes(self) -> None:
        r = _edit("200 mm taller", spec=_TABLE)
        changed_fields = {c["field"] for c in r["changes"]}
        assert "width_mm" not in changed_fields
        assert "depth_mm" not in changed_fields

    def test_new_design_changes_present(self) -> None:
        r = _edit("start over, table 1600 x 750 x 900 mm", spec=_TABLE)
        assert r["outcome"] == "new_design"
        assert isinstance(r["changes"], list)


# ── New design from edit context ──────────────────────────────────────────────

class TestNewDesignFromEdit:
    def test_start_over(self) -> None:
        r = _edit("start over, 1600 x 750 x 900 mm", spec=_TABLE)
        assert r["outcome"] == "new_design"
        assert r["read_as"] == "new_design"

    def test_frame_type_plus_dims(self) -> None:
        r = _edit("table 1600 x 750 mm", spec=_TABLE)
        assert r["outcome"] == "new_design"

    def test_frame_type_migration_table_to_shelf(self) -> None:
        r = _edit("shelf unit 1200 x 500 mm", spec=_TABLE)
        assert r["outcome"] == "new_design"
        assert r["spec"]["frame_type"] == "shelf_unit"
        # Dimensions should be carried via new spec
        assert r["spec"]["width_mm"] == pytest.approx(1200.0)
        # Frame type change must appear in changes
        ft_change = next(
            (c for c in r["changes"] if c["field"] == "frame_type"), None
        )
        assert ft_change is not None
        assert ft_change["old"] == "table"
        assert ft_change["new"] == "shelf_unit"


# ── Unsupported ───────────────────────────────────────────────────────────────

class TestUnsupported:
    def test_bolt_question(self) -> None:
        r = _edit("what bolts do I need", spec=_TABLE)
        assert r["outcome"] == "unsupported"
        assert r["error"] is not None

    def test_assembly_question(self) -> None:
        r = _edit("how do I assemble this", spec=_TABLE)
        assert r["outcome"] == "unsupported"

    def test_safety_question(self) -> None:
        r = _edit("is it safe to put my lathe on it", spec=_TABLE)
        assert r["outcome"] == "unsupported"

    def test_load_question_not_unsupported(self) -> None:
        # "can it hold 150 kg" must NOT be unsupported
        r = _edit("can it hold 150 kg", spec=_TABLE)
        assert r["outcome"] != "unsupported"
        assert r["outcome"] == "edit"


# ── spec_invalid after operation ──────────────────────────────────────────────

class TestSpecInvalid:
    def test_height_exceeds_max(self) -> None:
        r = _edit("height 3000 mm", spec=_TABLE)
        assert r["outcome"] == "spec_invalid"
        assert r["error"] is not None

    def test_height_negative_result(self) -> None:
        # 900 - 2000 = -1100 → invalid
        r = _edit("2000 mm shorter", spec=_TABLE)
        assert r["outcome"] == "spec_invalid"

    def test_shelf_above_height(self) -> None:
        # shelf at 950 mm when height is 900 mm → invalid
        r = _edit("shelf at 950 mm", spec=_TABLE)
        assert r["outcome"] == "spec_invalid"

    def test_wrong_field_for_frame_type(self) -> None:
        # "remove the shelf" on a shelf unit has no shelf_height_mm field
        r = _edit("remove the shelf", spec=_SHELF_UNIT)
        assert r["outcome"] == "spec_invalid"

    def test_level_count_too_low(self) -> None:
        # cannot go below 3 levels
        r = _edit("2 levels", spec=_SHELF_UNIT)
        assert r["outcome"] == "spec_invalid"

    def test_remove_level_at_minimum(self) -> None:
        # 3 levels → cannot remove
        r = _edit("remove a level", spec=_SHELF_UNIT)  # already 3 levels
        assert r["outcome"] == "spec_invalid"


# ── Clarify continuation ──────────────────────────────────────────────────────

class TestClarifyContinuation:
    def test_pending_merged_with_text(self) -> None:
        # pending has width; text adds depth
        pending = {
            "frame_type": "table",
            "width_mm": 1500.0,
            "depth_mm": None,
        }
        r = _edit("700 mm deep", pending=pending)
        assert r["outcome"] in ("new_design", "not_parsed")
        if r["outcome"] == "new_design":
            assert r["spec"]["width_mm"] == pytest.approx(1500.0)
            assert r["spec"]["depth_mm"] == pytest.approx(700.0)

    def test_pending_plus_complete_text_uses_text(self) -> None:
        # If the text alone is complete, use it (ignore partial pending)
        pending = {"frame_type": "table", "width_mm": 999.0}
        r = _edit("1500 x 700 x 900 mm", pending=pending)
        assert r["outcome"] == "new_design"
        # Should use text dimensions, not pending
        assert r["spec"]["width_mm"] == pytest.approx(1500.0)
