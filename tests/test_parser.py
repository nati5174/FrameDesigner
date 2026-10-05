from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from framegen.parser import ParseResult, parse
from framegen.parser import llm as llm_mod
from framegen.parser.llm import parse as llm_parse
from framegen.parser.rule_based import parse as rb_parse

# ── Helpers ───────────────────────────────────────────────────────────────────

def _rb(text: str) -> ParseResult:
    """Rule-based parse (via dispatcher pre-checks + rule_based)."""
    return parse.__wrapped__(text) if hasattr(parse, "__wrapped__") else rb_parse(text)


def _mock_llm(response_json: dict[str, Any]) -> MagicMock:
    """Build a mock Anthropic client that returns the given JSON."""
    content_block = MagicMock()
    content_block.text = json.dumps(response_json)
    msg = MagicMock()
    msg.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


# ── Pre-checks (dispatcher) ───────────────────────────────────────────────────

class TestImperialPreCheck:
    def test_double_quote(self) -> None:
        r = parse('60" x 28" x 36"')
        assert r.outcome == "spec_invalid"
        assert "Imperial" in (r.error or "")

    def test_ft_suffix(self) -> None:
        r = parse("5ft wide, 2ft deep, 3ft tall")
        assert r.outcome == "spec_invalid"

    def test_in_as_word_not_unit(self) -> None:
        # "1500 in width" — "in" is not immediately after a digit as a unit
        r = parse("1500 in width, 700 deep, 900 tall")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1500.0)

    def test_feet_word(self) -> None:
        r = parse("4 feet wide, 2 feet deep, 3 feet tall")
        assert r.outcome == "spec_invalid"

    def test_inches_word(self) -> None:
        r = parse("60 inches x 28 inches x 36 inches")
        assert r.outcome == "spec_invalid"


class TestEnclosurePreCheck:
    def test_enclosed(self) -> None:
        r = parse("enclosed cabinet 1500mm x 700mm x 900mm")
        assert r.outcome == "spec_invalid"
        assert "Enclosure" in (r.error or "")

    def test_toolbox_not_rejected(self) -> None:
        r = parse("bench to hold my toolbox, 1500 x 700 x 900 mm")
        assert r.outcome == "spec_valid"

    def test_box_standalone(self) -> None:
        r = parse("storage box 1500mm x 700mm x 900mm")
        assert r.outcome == "spec_invalid"


# ── Rule-based: canonical forms ───────────────────────────────────────────────

class TestCanonical:
    def test_mm_x_block(self) -> None:
        r = rb_parse("1500mm x 700mm x 900mm")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == 1500
        assert r.spec.depth_mm == 700
        assert r.spec.height_mm == 900

    def test_keyword_order_independent(self) -> None:
        r = rb_parse("900mm tall, 1500mm wide, 700mm deep")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == 1500
        assert r.spec.height_mm == 900

    def test_bare_integers_positional(self) -> None:
        r = rb_parse("1500 x 700 x 900")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == 1500

    def test_long_maps_to_width(self) -> None:
        r = rb_parse("1800mm long 600mm wide 900mm tall")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == 1800
        assert r.spec.depth_mm == 600


# ── Rule-based: unit conversion ───────────────────────────────────────────────

class TestUnitConversion:
    def test_cm(self) -> None:
        r = rb_parse("150cm x 70cm x 90cm")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1500.0)
        assert r.spec.depth_mm == pytest.approx(700.0)
        assert r.spec.height_mm == pytest.approx(900.0)

    def test_m(self) -> None:
        r = rb_parse("1.5m wide, 0.7m deep, 0.9m tall")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1500.0)

    def test_mixed_units(self) -> None:
        r = rb_parse("1.5m x 700mm x 90cm")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1500.0)
        assert r.spec.depth_mm == pytest.approx(700.0)
        assert r.spec.height_mm == pytest.approx(900.0)


# ── Rule-based: load ──────────────────────────────────────────────────────────

class TestLoad:
    def test_kg_suffix(self) -> None:
        r = rb_parse("1500mm x 700mm x 900mm, 200kg")
        assert r.spec is not None
        assert r.spec.target_load_kg == pytest.approx(200.0)

    def test_holds_keyword(self) -> None:
        r = rb_parse("table 1500 x 700 x 900 mm, holds 150kg")
        assert r.spec is not None
        assert r.spec.target_load_kg == pytest.approx(150.0)

    def test_kilograms_word(self) -> None:
        r = rb_parse("1500mm wide by 700mm deep by 900mm high, can hold 80 kilograms")
        assert r.spec is not None
        assert r.spec.target_load_kg == pytest.approx(80.0)

    def test_default_load(self) -> None:
        r = rb_parse("1500mm x 700mm x 900mm")
        assert r.spec is not None
        assert r.spec.target_load_kg == pytest.approx(100.0)
        assert "target_load_kg=100" in r.defaults_applied


# ── Rule-based: defaults ──────────────────────────────────────────────────────

class TestDefaults:
    def test_height_default(self) -> None:
        r = rb_parse("workbench 1500 x 700 mm")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.height_mm == pytest.approx(900.0)
        assert "height_mm=900" in r.defaults_applied

    def test_shelf_keyword_no_height(self) -> None:
        r = rb_parse("1500x700 bench, lower shelf")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.shelf_height_mm == pytest.approx(300.0)
        assert "shelf_height_mm=300" in r.defaults_applied

    def test_explicit_shelf_not_defaulted(self) -> None:
        r = rb_parse("1500mm x 700mm x 900mm, shelf at 400mm")
        assert r.spec is not None
        assert r.spec.shelf_height_mm == pytest.approx(400.0)
        assert "shelf_height_mm=300" not in r.defaults_applied


# ── Rule-based: rejections ────────────────────────────────────────────────────

class TestRuleBasedRejections:
    def test_unitless_small_in_block(self) -> None:
        r = rb_parse("table 50 x 70 x 90")
        assert r.outcome == "spec_invalid"
        assert "ambiguous" in (r.error or "").lower()

    def test_unitless_small_with_keyword(self) -> None:
        r = rb_parse("50mm wide 70mm deep 900mm tall")
        # 50mm is fine — it has a unit suffix; should parse
        assert r.outcome == "spec_valid"

    def test_two_shelves_becomes_shelf_unit(self) -> None:
        from framegen.spec import ShelfUnitSpec
        r = rb_parse("1500mm x 700mm x 900mm, shelf at 300mm and 600mm")
        assert r.outcome == "spec_valid"
        assert isinstance(r.spec, ShelfUnitSpec)
        assert r.spec.level_heights_mm == [300.0, 600.0, 900.0]

    def test_shelf_above_height(self) -> None:
        r = rb_parse("1500mm x 700mm x 900mm, shelf at 950mm")
        assert r.outcome == "spec_invalid"

    def test_stray_number_gives_not_parsed(self) -> None:
        # "4 legs" — "4" is unassigned
        r = rb_parse("1500mm x 700mm x 900mm table, 4 legs")
        assert r.outcome == "not_parsed"

    def test_missing_width_not_parsed(self) -> None:
        r = rb_parse("make me a table")
        assert r.outcome == "not_parsed"

    def test_metres_block_hits_sanity_limit(self) -> None:
        # "750 metres" propagates metres to all → width 900 000 mm → spec_invalid
        r = rb_parse("900 x 450 x 750 metres")
        assert r.outcome == "spec_invalid"
        assert r.error is not None  # non-empty error message


# ── Shelf-unit signal phrases ─────────────────────────────────────────────────

class TestShelfUnitSignals:
    """Word-number counts and 'per level' must not be silently dropped as table."""

    def test_word_count_becomes_shelf_unit(self) -> None:
        from framegen.spec import ShelfUnitSpec
        # "four levels" + "per level" — the original bug
        r = rb_parse("2000 x 400 x 1800, four levels, 80 kg per level")
        assert r.outcome == "spec_valid", f"got {r.outcome}: {r.error}"
        assert isinstance(r.spec, ShelfUnitSpec), "must be ShelfUnitSpec, not table"
        assert r.spec.load_per_level_kg == pytest.approx(80.0)
        assert r.spec.level_heights_mm is not None
        assert len(r.spec.level_heights_mm) == 4

    def test_per_level_only_becomes_shelf_unit(self) -> None:
        from framegen.spec import ShelfUnitSpec
        # "per level" alone (no word count) is enough to signal shelf unit
        r = rb_parse("1200 x 500 x 1800, 50 kg per level")
        assert r.outcome == "spec_valid", f"got {r.outcome}: {r.error}"
        assert isinstance(r.spec, ShelfUnitSpec)
        assert r.spec.load_per_level_kg == pytest.approx(50.0)

    def test_digit_count_word_load(self) -> None:
        from framegen.spec import ShelfUnitSpec
        # digit count, no word number — existing capability; load on per-level phrase
        r = rb_parse("900 x 400 x 1800, 3 levels, 30 kg per level")
        assert r.outcome == "spec_valid"
        assert isinstance(r.spec, ShelfUnitSpec)
        assert len(r.spec.level_heights_mm) == 3  # type: ignore[arg-type]

    def test_word_count_too_few_is_invalid(self) -> None:
        # 2 < minimum 3 → spec_invalid (count must not be silently clamped)
        r = rb_parse("1500 x 700 with 2 shelves")
        assert r.outcome == "spec_invalid"

    def test_word_count_too_many_is_invalid(self) -> None:
        # 12 > maximum 10 → spec_invalid
        r = rb_parse("shelf unit 900 x 400 x 2000, 12 levels")
        assert r.outcome == "spec_invalid"

    def test_table_word_shelves_plural_is_invalid(self) -> None:
        # table word + "shelves" plural, no count/heights → spec_invalid
        r = rb_parse("workbench with shelves, 1500 x 700")
        assert r.outcome == "spec_invalid"
        assert r.error is not None
        assert "shelves" in r.error.lower()

    def test_shelves_plural_no_table_word_not_parsed(self) -> None:
        # "shelves" plural without table word → rule parser can't decide → not_parsed
        r = rb_parse("bookshelves 1500 x 700")
        assert r.outcome == "not_parsed"

    def test_table_word_with_count_becomes_shelf_unit_h900(self) -> None:
        # Table word + count → shelf unit with H=900 (table-word height rule)
        from framegen.spec import ShelfUnitSpec
        r = rb_parse("workbench 1500 x 700 with 3 shelves")
        assert r.outcome == "spec_valid", f"got {r.outcome}: {r.error}"
        assert isinstance(r.spec, ShelfUnitSpec)
        assert r.spec.height_mm == pytest.approx(900.0)
        assert r.spec.level_heights_mm == [300.0, 600.0, 900.0]

    def test_singular_shelf_still_works(self) -> None:
        # "shelf" singular (single under-shelf on table) must still work
        r = rb_parse("1500x700 bench, lower shelf")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.shelf_height_mm == pytest.approx(300.0)  # type: ignore[union-attr]


# ── LLM parser (mocked) ───────────────────────────────────────────────────────

class TestLLMParser:
    def setup_method(self) -> None:
        self._orig = llm_mod._client
        llm_mod.set_client(None)  # disables auto-init from env for this test

    def teardown_method(self) -> None:
        llm_mod._client = self._orig
        llm_mod._client_set_explicitly = False

    def test_valid_response(self) -> None:
        mock = _mock_llm({"width_mm": 1500, "depth_mm": 700, "height_mm": 900,
                          "shelf_height_mm": None, "target_load_kg": None})
        llm_mod.set_client(mock)  # type: ignore[arg-type]
        r = llm_parse("workbench one and a half metres wide")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1500.0)
        assert r.spec.target_load_kg == pytest.approx(100.0)
        assert "target_load_kg=100" in r.defaults_applied

    def test_height_null_applies_default(self) -> None:
        mock = _mock_llm({"width_mm": 1500, "depth_mm": 700, "height_mm": None,
                          "shelf_height_mm": None, "target_load_kg": None})
        llm_mod.set_client(mock)  # type: ignore[arg-type]
        r = llm_parse("workbench 1500mm x 700mm")
        assert r.spec is not None
        assert r.spec.height_mm == pytest.approx(900.0)
        assert "height_mm=900" in r.defaults_applied

    def test_insufficient_information(self) -> None:
        mock = _mock_llm({"result": "insufficient_information"})
        llm_mod.set_client(mock)  # type: ignore[arg-type]
        r = llm_parse("make me a table")
        assert r.outcome == "not_parsed"

    def test_unsupported_result(self) -> None:
        mock = _mock_llm({"result": "unsupported",
                          "reason": "Imperial units are not supported."})
        llm_mod.set_client(mock)  # type: ignore[arg-type]
        r = llm_parse("60 inches wide")
        assert r.outcome == "spec_invalid"
        assert "Imperial" in (r.error or "")

    def test_malformed_json_retries(self) -> None:
        content1 = MagicMock()
        content1.text = "not json at all"
        content2 = MagicMock()
        content2.text = json.dumps({"width_mm": 1500, "depth_mm": 700,
                                    "height_mm": 900, "shelf_height_mm": None,
                                    "target_load_kg": None})
        msg1 = MagicMock()
        msg1.content = [content1]
        msg2 = MagicMock()
        msg2.content = [content2]
        client = MagicMock()
        client.messages.create.side_effect = [msg1, msg2]
        llm_mod.set_client(client)  # type: ignore[arg-type]
        r = llm_parse("workbench 1.5m x 0.7m x 0.9m")
        assert r.outcome == "spec_valid"
        assert client.messages.create.call_count == 2

    def test_validation_failure_no_retry(self) -> None:
        # shelf >= height → spec_invalid without retrying
        mock = _mock_llm({"width_mm": 1500, "depth_mm": 700, "height_mm": 900,
                          "shelf_height_mm": 950, "target_load_kg": None})
        llm_mod.set_client(mock)  # type: ignore[arg-type]
        r = llm_parse("1500mm x 700mm x 900mm, shelf at 950mm")
        assert r.outcome == "spec_invalid"
        assert mock.messages.create.call_count == 1

    def test_no_api_key_returns_not_parsed(self) -> None:
        # Client is None (no key set)
        llm_mod.set_client(None)
        r = llm_parse("workbench 1500mm x 700mm x 900mm")
        assert r.outcome == "not_parsed"

    def test_code_fence_stripped(self) -> None:
        content = MagicMock()
        content.text = (
            '```json\n{"width_mm":1500,"depth_mm":700,'
            '"height_mm":900,"shelf_height_mm":null,"target_load_kg":null}\n```'
        )
        msg = MagicMock()
        msg.content = [content]
        client = MagicMock()
        client.messages.create.return_value = msg
        llm_mod.set_client(client)  # type: ignore[arg-type]
        r = llm_parse("1500mm x 700mm x 900mm")
        assert r.outcome == "spec_valid"


# ── Bug regressions: spelled-out unit names in block ─────────────────────────

class TestSpelledOutUnitsInBlock:
    """_BLOCK_RE used m(?!m) which matched the leading 'm' of 'millimetres'."""

    def test_millimetres_block_height(self) -> None:
        # Before fix: H was 750 000 mm (first 'm' of 'millimetres' grabbed as metres)
        r = rb_parse("table 1400 x 600 x 750 millimetres")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.height_mm == pytest.approx(750.0)

    def test_millimeters_american_spelling(self) -> None:
        r = rb_parse("bench 1200 x 500 x 850 millimeters")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.height_mm == pytest.approx(850.0)

    def test_centimetres_block_all_three(self) -> None:
        r = rb_parse("frame 120 x 50 x 75 centimetres")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1200.0)
        assert r.spec.depth_mm == pytest.approx(500.0)
        assert r.spec.height_mm == pytest.approx(750.0)


# ── Bug regressions: trailing unit in positional block ────────────────────────

class TestTrailingBlockUnit:
    """Trailing unit on last block token must apply to all bare preceding tokens."""

    def test_trailing_cm_two_values(self) -> None:
        # Before fix: W was 150 mm (cm applied only to 60, not 150)
        r = rb_parse("workbench 150 x 60 cm")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1500.0)
        assert r.spec.depth_mm == pytest.approx(600.0)

    def test_trailing_m_two_values(self) -> None:
        # '2' is bare < 100; without propagation this hits unitless-small → spec_invalid
        r = rb_parse("table 2 x 0.7 m")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(2000.0)
        assert r.spec.depth_mm == pytest.approx(700.0)

    def test_trailing_cm_three_values(self) -> None:
        r = rb_parse("frame 180 x 60 x 90 cm")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1800.0)
        assert r.spec.depth_mm == pytest.approx(600.0)
        assert r.spec.height_mm == pytest.approx(900.0)

    def test_per_token_units_not_propagated(self) -> None:
        # Each number has its own unit — no propagation should occur
        r = rb_parse("1.5m x 700mm x 90cm")
        assert r.outcome == "spec_valid"
        assert r.spec is not None
        assert r.spec.width_mm == pytest.approx(1500.0)
        assert r.spec.depth_mm == pytest.approx(700.0)
        assert r.spec.height_mm == pytest.approx(900.0)


# ── Dispatcher integration ────────────────────────────────────────────────────

class TestDispatcher:
    def setup_method(self) -> None:
        self._orig = llm_mod._client

    def teardown_method(self) -> None:
        llm_mod._client = self._orig
        llm_mod._client_set_explicitly = False

    def test_rule_based_wins_without_llm(self) -> None:
        llm_mod.set_client(None)
        r = parse("1500mm x 700mm x 900mm")
        assert r.outcome == "spec_valid"
        assert r.parser_used == "rule_based"

    def test_not_parsed_falls_through_to_llm(self) -> None:
        mock = _mock_llm({"width_mm": 1500, "depth_mm": 700, "height_mm": 900,
                          "shelf_height_mm": None, "target_load_kg": None})
        llm_mod.set_client(mock)  # type: ignore[arg-type]
        r = parse("1500mm x 700mm x 900mm table, 4 legs")
        assert r.outcome == "spec_valid"
        assert r.parser_used == "llm"

    def test_spec_invalid_not_sent_to_llm(self) -> None:
        llm_mod.set_client(MagicMock())
        r = parse('60" x 28" x 36"')
        assert r.outcome == "spec_invalid"
        # LLM should not have been called
        assert llm_mod._client is not None
        llm_mod._client.messages.create.assert_not_called()  # type: ignore[union-attr]
