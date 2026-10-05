from __future__ import annotations

import json
import os
import unittest.mock
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from framegen.api import app
from framegen.parser import llm as llm_mod

client = TestClient(app)


# ── Helpers shared with parse tests ───────────────────────────────────────────

def _mock_llm(response_json: dict[str, Any]) -> MagicMock:
    content_block = MagicMock()
    content_block.text = json.dumps(response_json)
    msg = MagicMock()
    msg.content = [content_block]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = msg
    return mock_client


def _mock_llm_error() -> MagicMock:
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("Connection timeout")
    return mock_client


# ── No shelf ──────────────────────────────────────────────────────────────────

def test_no_shelf_status() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    assert resp.status_code == 200


def test_no_shelf_bar_count() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    bars = resp.json()["bars"]
    assert len(bars) == 8


def test_no_shelf_roles() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    bars = resp.json()["bars"]
    by_role: dict[str, int] = {}
    for bar in bars:
        by_role[bar["role"]] = by_role.get(bar["role"], 0) + 1
    assert by_role["leg"] == 4
    assert by_role["top_rail_width"] == 2
    assert by_role["top_rail_depth"] == 2


def test_no_shelf_lengths() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    bars = resp.json()["bars"]
    # derive length from start/end coordinates
    import math
    def length(b: dict) -> float:  # type: ignore[type-arg]
        s, e = b["start"], b["end"]
        return math.dist(s, e)

    by_role: dict[str, list[float]] = {}
    for bar in bars:
        by_role.setdefault(bar["role"], []).append(round(length(bar), 6))

    assert sorted(by_role["leg"]) == [900.0, 900.0, 900.0, 900.0]
    assert sorted(by_role["top_rail_width"]) == [1420.0, 1420.0]
    assert sorted(by_role["top_rail_depth"]) == [620.0, 620.0]


def test_no_shelf_cut_list_total() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    rows = resp.json()["cut_list"]
    total = sum(r["total_mm"] for r in rows)
    assert total == 7680.0


def test_bar_coordinates_are_triples() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    for bar in resp.json()["bars"]:
        assert len(bar["start"]) == 3
        assert len(bar["end"]) == 3
        assert all(isinstance(v, (int, float)) for v in bar["start"])
        assert all(isinstance(v, (int, float)) for v in bar["end"])


# ── With shelf ────────────────────────────────────────────────────────────────

def test_with_shelf_bar_count() -> None:
    resp = client.get(
        "/frame", params={"width": 1500, "depth": 700, "height": 900, "shelf": 300}
    )
    assert len(resp.json()["bars"]) == 12


def test_with_shelf_cut_list_total() -> None:
    resp = client.get(
        "/frame", params={"width": 1500, "depth": 700, "height": 900, "shelf": 300}
    )
    rows = resp.json()["cut_list"]
    total = sum(r["total_mm"] for r in rows)
    assert total == 11760.0


# ── Centre legs ───────────────────────────────────────────────────────────────

_CL_PARAMS = {"width": 3000, "depth": 700, "height": 900, "centre_legs": "true"}


def test_centre_legs_bar_count() -> None:
    resp = client.get("/frame", params=_CL_PARAMS)
    assert resp.status_code == 200
    bars = resp.json()["bars"]
    # 4 corner legs + 2 centre legs + 4 width half-rails + 2 depth rails = 12
    assert len(bars) == 12


def test_centre_legs_roles() -> None:
    resp = client.get("/frame", params=_CL_PARAMS)
    bars = resp.json()["bars"]
    by_role: dict[str, int] = {}
    for bar in bars:
        by_role[bar["role"]] = by_role.get(bar["role"], 0) + 1
    assert by_role["leg"] == 4
    assert by_role["centre_leg"] == 2
    assert by_role["top_rail_width"] == 4
    assert by_role["top_rail_depth"] == 2


def test_centre_legs_cut_list() -> None:
    """3000×700×900 with centre legs: 6 legs@900, 4 width rails@1440, 2 depth rails@620.
    Total = 6*900 + 4*1440 + 2*620 = 5400 + 5760 + 1240 = 12400 mm."""
    resp = client.get("/frame", params=_CL_PARAMS)
    rows = resp.json()["cut_list"]
    total = sum(r["total_mm"] for r in rows)
    assert total == 12400.0
    lengths = sorted(r["length_mm"] for r in rows)
    # 620 (qty 2), 900 (qty 6), 1440 (qty 4) → rows sorted by length
    assert lengths == [620.0, 900.0, 1440.0]
    qty_by_len = {r["length_mm"]: r["qty"] for r in rows}
    assert qty_by_len[900.0] == 6
    assert qty_by_len[1440.0] == 4
    assert qty_by_len[620.0] == 2


def test_centre_legs_with_shelf_cut_list() -> None:
    """3000×700×900, shelf@300, centre_legs.
    8 width half-rails@1440, 4 depth rails@620, 6 legs@900.
    Total = 8*1440 + 4*620 + 6*900 = 11520 + 2480 + 5400 = 19400 mm."""
    resp = client.get(
        "/frame",
        params={
            "width": 3000, "depth": 700, "height": 900,
            "shelf": 300, "centre_legs": "true",
        },
    )
    assert resp.status_code == 200
    rows = resp.json()["cut_list"]
    total = sum(r["total_mm"] for r in rows)
    assert total == 19400.0


def test_centre_legs_load_check_worked_example() -> None:
    """Worked example: σ=12.81 MPa, δ=2.01 mm vs allowables 57.46 MPa, 4.80 mm."""
    resp = client.get("/frame", params=_CL_PARAMS)
    load = resp.json()["check_report"]["load"]
    assert load["passed"] is True
    gov = load["governing_rail"]
    dist = gov["distributed"]
    import pytest
    assert dist["bending_stress_mpa"] == pytest.approx(12.81, abs=0.01)
    assert dist["deflection_mm"] == pytest.approx(2.01, abs=0.01)
    assert gov["allowable_stress_mpa"] == pytest.approx(57.46, abs=0.01)
    assert gov["deflection_limit_mm"] == pytest.approx(4.80, abs=0.01)


def test_centre_legs_too_narrow_returns_400() -> None:
    resp = client.get(
        "/frame",
        params={"width": 100, "depth": 700, "height": 900, "centre_legs": "true"},
    )
    assert resp.status_code == 400


# ── Error cases ───────────────────────────────────────────────────────────────

def test_shelf_above_height_returns_400() -> None:
    resp = client.get(
        "/frame", params={"width": 1500, "depth": 700, "height": 900, "shelf": 950}
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]  # non-empty error message


def test_unknown_series_returns_400() -> None:
    resp = client.get(
        "/frame",
        params={"width": 1500, "depth": 700, "height": 900, "series": "99-series"},
    )
    assert resp.status_code == 400
    assert "unknown series" in resp.json()["detail"]


# ── Check report ───────────────────────────────────────────────────────────────

def test_check_report_present_in_response() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    assert resp.status_code == 200
    assert "check_report" in resp.json()


def test_check_report_structure() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    cr = resp.json()["check_report"]
    assert "collision" in cr
    assert "connectivity" in cr
    assert "load" in cr
    assert "passed" in cr


def test_check_report_load_is_estimate() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    load = resp.json()["check_report"]["load"]
    assert load["is_estimate"] is True
    assert load["status"] == "evaluated"


def test_check_report_governing_rail_present() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    load = resp.json()["check_report"]["load"]
    assert load["governing_rail"] is not None
    assert load["governing_rail"]["role"] == "top_rail_width"


def test_check_report_valid_frame_passes() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    cr = resp.json()["check_report"]
    assert cr["collision"]["passed"] is True
    assert cr["connectivity"]["passed"] is True
    assert cr["load"]["passed"] is True


# ── /parse endpoint ────────────────────────────────────────────────────────────

class TestParseEndpoint:
    def setup_method(self) -> None:
        self._orig = llm_mod._client
        llm_mod.set_client(None)  # disables auto-init from env for this test

    def teardown_method(self) -> None:
        llm_mod._client = self._orig
        llm_mod._client_set_explicitly = False

    # -- rule-based paths (no LLM needed) --------------------------------------

    def test_rule_based_valid(self) -> None:
        resp = client.post(
            "/parse", json={"text": "workbench 1500 x 700 mm, 900 mm tall"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "spec_valid"
        assert data["parser_used"] == "rule_based"
        assert data["spec"]["width_mm"] == 1500.0
        assert data["spec"]["depth_mm"] == 700.0
        assert data["spec"]["height_mm"] == 900.0

    def test_rule_based_with_shelf(self) -> None:
        resp = client.post(
            "/parse", json={"text": "1500 x 700 x 900 mm, shelf at 300 mm"}
        )
        data = resp.json()
        assert data["outcome"] == "spec_valid"
        assert data["spec"]["shelf_height_mm"] == 300.0

    def test_spec_invalid_imperial(self) -> None:
        resp = client.post("/parse", json={"text": "60 inches wide, 28 inches deep"})
        data = resp.json()
        assert data["outcome"] == "spec_invalid"
        assert "Imperial" in (data["error"] or "")

    def test_spec_invalid_enclosure(self) -> None:
        resp = client.post("/parse", json={"text": "build me a box 1000 x 500 mm"})
        data = resp.json()
        assert data["outcome"] == "spec_invalid"

    # -- text length cap -------------------------------------------------------

    def test_text_too_long_returns_422(self) -> None:
        resp = client.post("/parse", json={"text": "x" * 501})
        assert resp.status_code == 422

    def test_text_at_limit_accepted(self) -> None:
        resp = client.post(
            "/parse", json={"text": "workbench 1500 x 700 mm" + " " * (500 - 23)}
        )
        assert resp.status_code == 200

    # -- llm_available field ---------------------------------------------------

    def test_llm_available_false_when_no_key(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            resp = client.post("/parse", json={"text": "1500 x 700 x 900 mm"})
        assert resp.json()["llm_available"] is False

    def test_llm_available_true_when_key_set(self) -> None:
        with unittest.mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            resp = client.post("/parse", json={"text": "1500 x 700 x 900 mm"})
        assert resp.json()["llm_available"] is True

    # -- LLM paths (mocked) ----------------------------------------------------

    def test_llm_valid(self) -> None:
        llm_mod.set_client(_mock_llm(  # type: ignore[arg-type]
            {"width_mm": 1500, "depth_mm": 700, "height_mm": 900,
             "shelf_height_mm": None, "target_load_kg": None}
        ))
        # Text that rule-based can't handle (stray token "table")
        resp = client.post(
            "/parse", json={"text": "1500mm x 700mm x 900mm table, 4 legs"}
        )
        data = resp.json()
        assert data["outcome"] == "spec_valid"
        assert data["parser_used"] == "llm"

    def test_llm_defaults_applied(self) -> None:
        llm_mod.set_client(_mock_llm(  # type: ignore[arg-type]
            {"width_mm": 1500, "depth_mm": 700, "height_mm": None,
             "shelf_height_mm": None, "target_load_kg": None}
        ))
        resp = client.post(
            "/parse", json={"text": "1500mm x 700mm x 900mm table, 4 legs"}
        )
        data = resp.json()
        assert data["outcome"] == "spec_valid"
        assert "height_mm=900" in data["defaults_applied"]

    def test_no_key_not_parsed(self) -> None:
        # LLM client stays None (set in setup_method); rule-based can't handle this
        resp = client.post("/parse", json={"text": "make me a frame please"})
        data = resp.json()
        assert data["outcome"] == "not_parsed"
        assert data["spec"] is None

    # -- LLM error handling ----------------------------------------------------

    def test_llm_error_returns_not_parsed_not_500(self) -> None:
        llm_mod.set_client(_mock_llm_error())  # type: ignore[arg-type]
        # Use text that rule-based can't handle so the LLM is actually called
        resp = client.post(
            "/parse", json={"text": "1500mm x 700mm x 900mm table, 4 legs"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "not_parsed"
        assert data["error"] is not None
        assert "LLM" in data["error"]

    # -- response shape --------------------------------------------------------

    def test_response_has_all_fields(self) -> None:
        resp = client.post("/parse", json={"text": "1500 x 700 x 900 mm"})
        data = resp.json()
        for field in ("outcome", "spec", "error", "defaults_applied",
                      "parser_used", "llm_available"):
            assert field in data
