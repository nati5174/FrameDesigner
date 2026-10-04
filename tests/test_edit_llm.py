"""Tests for the LLM edit parser (edit_llm.py)."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from framegen.parser.edit_llm import (
    _interpret,
    parse_edit_with_spec,
    parse_first_turn,
    set_client,
)
from framegen.spec import TableSpec

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def table_spec() -> TableSpec:
    return TableSpec(
        frame_type="table",
        width_mm=1500.0,
        depth_mm=700.0,
        height_mm=900.0,
        profile_series="20",
        shelf_height_mm=None,
        target_load_kg=75.0,
        centre_legs=False,
    )


def _make_client(response_json: dict[str, Any]) -> MagicMock:
    """Return a mock Anthropic client that returns a given JSON response."""
    content = MagicMock()
    content.text = json.dumps(response_json)
    msg = MagicMock()
    msg.content = [content]
    messages = MagicMock()
    messages.create.return_value = msg
    client = MagicMock()
    client.messages = messages
    return client


# ── _interpret unit tests ─────────────────────────────────────────────────────

class TestInterpret:
    def test_operations(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "height_mm", "op": "add", "value": 200.0},
            ]
        })
        result = _interpret(raw)
        assert result is not None
        assert result.outcome == "operations"
        assert len(result.operations) == 1
        assert result.operations[0].field == "height_mm"
        assert result.operations[0].op == "add"
        assert result.operations[0].value == pytest.approx(200.0)

    def test_new_design(self) -> None:
        raw = json.dumps({"result": "new_design"})
        result = _interpret(raw)
        assert result is not None
        assert result.outcome == "new_design"

    def test_unsupported(self) -> None:
        raw = json.dumps({"result": "unsupported", "reason": "assembly question"})
        result = _interpret(raw)
        assert result is not None
        assert result.outcome == "unsupported"
        assert result.unsupported_reason == "assembly question"

    def test_insufficient_information(self) -> None:
        raw = json.dumps({
            "result": "insufficient_information",
            "missing": ["depth_mm"],
        })
        result = _interpret(raw)
        assert result is not None
        assert result.outcome == "clarify"
        assert result.missing == ["depth_mm"]

    def test_malformed_json(self) -> None:
        assert _interpret("not json") is None

    def test_malformed_no_key(self) -> None:
        assert _interpret(json.dumps({"unknown": "key"})) is None

    def test_code_fence_stripped(self) -> None:
        raw = "```json\n" + json.dumps({"result": "new_design"}) + "\n```"
        result = _interpret(raw)
        assert result is not None
        assert result.outcome == "new_design"

    def test_operations_bool_centre_legs(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "centre_legs", "op": "set", "value": True},
            ]
        })
        result = _interpret(raw)
        assert result is not None
        assert result.outcome == "operations"
        assert result.operations[0].value is True

    def test_operations_set_null(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "shelf_height_mm", "op": "set", "value": None},
            ]
        })
        result = _interpret(raw)
        assert result is not None
        assert result.operations[0].value is None

    def test_operations_add_level(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "level_heights_mm", "op": "add_level", "value": 600.0},
            ]
        })
        result = _interpret(raw)
        assert result is not None
        assert result.operations[0].op == "add_level"

    def test_operations_remove_level(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "level_heights_mm", "op": "remove_level", "value": None},
            ]
        })
        result = _interpret(raw)
        assert result is not None
        assert result.operations[0].op == "remove_level"

    def test_operations_set_level_count(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "level_heights_mm", "op": "set_level_count", "value": 5},
            ]
        })
        result = _interpret(raw)
        assert result is not None
        assert result.operations[0].op == "set_level_count"
        assert result.operations[0].value == pytest.approx(5.0)

    def test_unknown_op_type_returns_none(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "height_mm", "op": "multiply", "value": 2},
            ]
        })
        assert _interpret(raw) is None

    def test_add_without_numeric_value_returns_none(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "height_mm", "op": "add", "value": "big"},
            ]
        })
        assert _interpret(raw) is None

    def test_missing_op_field_returns_none(self) -> None:
        raw = json.dumps({
            "operations": [
                {"field": "height_mm", "value": 900},
            ]
        })
        assert _interpret(raw) is None

    def test_insufficient_missing_non_list(self) -> None:
        raw = json.dumps({
            "result": "insufficient_information",
            "missing": "depth_mm",
        })
        result = _interpret(raw)
        assert result is not None
        assert result.missing == []


# ── parse_edit_with_spec ──────────────────────────────────────────────────────

class TestParseEditWithSpec:
    def test_operations_returned(self, table_spec: TableSpec) -> None:
        client = _make_client({
            "operations": [{"field": "height_mm", "op": "add", "value": 100.0}]
        })
        set_client(client)
        try:
            result = parse_edit_with_spec("100 mm taller please", table_spec)
        finally:
            set_client(None)
        assert result.outcome == "operations"
        assert result.operations[0].field == "height_mm"

    def test_no_client_returns_not_matched(self, table_spec: TableSpec) -> None:
        set_client(None)
        result = parse_edit_with_spec("something unclear", table_spec)
        assert result.outcome == "not_matched"

    def test_new_design_signal(self, table_spec: TableSpec) -> None:
        client = _make_client({"result": "new_design"})
        set_client(client)
        try:
            result = parse_edit_with_spec("start over", table_spec)
        finally:
            set_client(None)
        assert result.outcome == "new_design"

    def test_unsupported(self, table_spec: TableSpec) -> None:
        client = _make_client({"result": "unsupported", "reason": "bolts question"})
        set_client(client)
        try:
            result = parse_edit_with_spec("what bolts do I need", table_spec)
        finally:
            set_client(None)
        assert result.outcome == "unsupported"
        assert result.unsupported_reason == "bolts question"

    def test_clarify_missing_fields(self, table_spec: TableSpec) -> None:
        client = _make_client({
            "result": "insufficient_information",
            "missing": ["height_mm"],
        })
        set_client(client)
        try:
            result = parse_edit_with_spec("make it taller", table_spec)
        finally:
            set_client(None)
        assert result.outcome == "clarify"
        assert "height_mm" in result.missing

    def test_malformed_then_retry_succeeds(self, table_spec: TableSpec) -> None:
        good_response = json.dumps({
            "operations": [{"field": "width_mm", "op": "set", "value": 2000.0}]
        })
        content1 = MagicMock()
        content1.text = "this is not json"
        content2 = MagicMock()
        content2.text = good_response
        msg1 = MagicMock()
        msg1.content = [content1]
        msg2 = MagicMock()
        msg2.content = [content2]
        messages = MagicMock()
        messages.create.side_effect = [msg1, msg2]
        client = MagicMock()
        client.messages = messages
        set_client(client)
        try:
            result = parse_edit_with_spec("set width to 2000", table_spec)
        finally:
            set_client(None)
        assert result.outcome == "operations"
        assert result.operations[0].value == pytest.approx(2000.0)

    def test_api_error_returns_not_matched(self, table_spec: TableSpec) -> None:
        messages = MagicMock()
        messages.create.side_effect = RuntimeError("network error")
        client = MagicMock()
        client.messages = messages
        set_client(client)
        try:
            result = parse_edit_with_spec("anything", table_spec)
        finally:
            set_client(None)
        assert result.outcome == "not_matched"


# ── parse_first_turn ──────────────────────────────────────────────────────────

class TestParseFirstTurn:
    def test_new_design(self) -> None:
        client = _make_client({"result": "new_design"})
        set_client(client)
        try:
            result = parse_first_turn("1500 x 700 mm table")
        finally:
            set_client(None)
        assert result.outcome == "new_design"

    def test_clarify(self) -> None:
        client = _make_client({
            "result": "insufficient_information",
            "missing": ["depth_mm"],
        })
        set_client(client)
        try:
            result = parse_first_turn("I need a frame 1500mm wide")
        finally:
            set_client(None)
        assert result.outcome == "clarify"
        assert "depth_mm" in result.missing

    def test_unsupported(self) -> None:
        client = _make_client({"result": "unsupported", "reason": "assembly"})
        set_client(client)
        try:
            result = parse_first_turn("how do I assemble this")
        finally:
            set_client(None)
        assert result.outcome == "unsupported"

    def test_no_client_returns_not_matched(self) -> None:
        set_client(None)
        result = parse_first_turn("something")
        assert result.outcome == "not_matched"

    def test_api_error_returns_not_matched(self) -> None:
        messages = MagicMock()
        messages.create.side_effect = RuntimeError("timeout")
        client = MagicMock()
        client.messages = messages
        set_client(client)
        try:
            result = parse_first_turn("anything")
        finally:
            set_client(None)
        assert result.outcome == "not_matched"
