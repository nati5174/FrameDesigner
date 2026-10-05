"""
Tests for rate limiting, daily SDK-call cap fallback, and secret leaking.

The autouse fixture in conftest.py resets the limiter and counter before
every test, so these tests are order-independent.
"""
from __future__ import annotations

import logging
import os
import unittest.mock
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from framegen import _llm_counter
from framegen.api import app
from framegen.parser import edit_llm as edit_llm_mod
from framegen.parser import llm as llm_mod

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────────────────────────

# Rule-based parseable text — no LLM is called, so no token spend.
_RB_TEXT = "1500 x 700 x 900 mm"

_TABLE_SPEC: dict[str, Any] = {
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

_FAILING_SPEC: dict[str, Any] = {
    **_TABLE_SPEC,
    "width_mm": 3000,
}

# IP headers used to isolate per-IP buckets between tests
_IP_A = {"X-Forwarded-For": "10.0.0.1"}
_IP_B = {"X-Forwarded-For": "10.0.0.2"}


# ── Per-IP rate limit ──────────────────────────────────────────────────────────

class TestPerIpRateLimit:
    def test_tenth_call_succeeds(self) -> None:
        for _ in range(10):
            r = client.post("/parse", json={"text": _RB_TEXT}, headers=_IP_A)
            assert r.status_code == 200

    def test_eleventh_call_returns_429(self) -> None:
        for _ in range(10):
            client.post("/parse", json={"text": _RB_TEXT}, headers=_IP_A)
        r = client.post("/parse", json={"text": _RB_TEXT}, headers=_IP_A)
        assert r.status_code == 429

    def test_different_ips_use_separate_buckets(self) -> None:
        for _ in range(10):
            client.post("/parse", json={"text": _RB_TEXT}, headers=_IP_A)
        r = client.post("/parse", json={"text": _RB_TEXT}, headers=_IP_B)
        assert r.status_code == 200


# ── Daily cap fallback ────────────────────────────────────────────────────────

class TestDailyCapFallback:
    def setup_method(self) -> None:
        # Monkeypatch the counter to DAILY_CAP so the very next call hits the cap
        _llm_counter._calls = _llm_counter.DAILY_CAP  # type: ignore[attr-defined]

        # Inject a mock LLM client so parse() tries to call the SDK
        self._orig_llm = llm_mod._client
        self._orig_llm_explicit = llm_mod._client_set_explicitly
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"width_mm":1500,"depth_mm":700}')]
        )
        llm_mod.set_client(mock_client)  # type: ignore[arg-type]

    def teardown_method(self) -> None:
        llm_mod._client = self._orig_llm
        llm_mod._client_set_explicitly = self._orig_llm_explicit
        _llm_counter.reset()

    def test_parse_returns_200_not_503(self) -> None:
        # Text that rule-based can't handle → dispatcher tries LLM → cap hit
        r = client.post("/parse", json={"text": "make me a frame please"})
        assert r.status_code == 200

    def test_parse_llm_available_false(self) -> None:
        with unittest.mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            r = client.post("/parse", json={"text": "make me a frame please"})
        assert r.json()["llm_available"] is False

    def test_parse_parser_used_rule_based(self) -> None:
        r = client.post("/parse", json={"text": "make me a frame please"})
        assert r.json()["parser_used"] == "rule_based"

    def test_parse_error_contains_cap_note(self) -> None:
        r = client.post("/parse", json={"text": "make me a frame please"})
        assert _llm_counter.CAP_NOTE in (r.json()["error"] or "")

    def test_rule_based_text_still_works(self) -> None:
        # Rule-based parseable text succeeds even when cap is hit
        r = client.post("/parse", json={"text": _RB_TEXT})
        assert r.status_code == 200
        assert r.json()["outcome"] == "spec_valid"

    def test_suggest_returns_unranked_candidates(self) -> None:
        # /suggest returns unranked suggestions (no LLM ranking) when cap is hit
        with unittest.mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            r = client.post(
                "/suggest",
                json={"spec": _FAILING_SPEC, "original_request": "workbench"},
            )
        assert r.status_code == 200
        # Suggestions are still returned (unranked), not an error
        assert isinstance(r.json()["suggestions"], list)


# ── Secret leak ───────────────────────────────────────────────────────────────

class TestNoSecretLeak:
    _FAKE_KEY = "sk-ant-test-secret-xyzzy-deadbeef"

    def setup_method(self) -> None:
        self._orig_llm = llm_mod._client
        self._orig_llm_explicit = llm_mod._client_set_explicitly
        self._orig_edit = edit_llm_mod._client
        self._orig_edit_explicit = edit_llm_mod._client_set_explicitly

        exc = Exception(f"API authentication failed with key: {self._FAKE_KEY}")
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = exc
        llm_mod.set_client(mock_client)  # type: ignore[arg-type]
        edit_llm_mod.set_client(mock_client)  # type: ignore[arg-type]

    def teardown_method(self) -> None:
        llm_mod._client = self._orig_llm
        llm_mod._client_set_explicitly = self._orig_llm_explicit
        edit_llm_mod._client = self._orig_edit
        edit_llm_mod._client_set_explicitly = self._orig_edit_explicit

    def _mock_anthropic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Also patch rank.py's anthropic.Anthropic so it raises with the key."""
        exc = Exception(f"API authentication failed with key: {self._FAKE_KEY}")
        mock_instance = MagicMock()
        mock_instance.messages.create.side_effect = exc
        monkeypatch.setattr(
            "anthropic.Anthropic",
            lambda **kwargs: mock_instance,
        )

    def test_key_absent_from_parse_response(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._FAKE_KEY)
        self._mock_anthropic(monkeypatch)
        with caplog.at_level(logging.INFO, logger="framegen"):
            r = client.post("/parse", json={"text": "make me a frame please"})
        assert self._FAKE_KEY not in r.text
        assert self._FAKE_KEY not in caplog.text

    def test_key_absent_from_edit_response(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._FAKE_KEY)
        self._mock_anthropic(monkeypatch)
        with caplog.at_level(logging.INFO, logger="framegen"):
            r = client.post(
                "/edit",
                json={"text": "make me a frame please"},
            )
        assert self._FAKE_KEY not in r.text
        assert self._FAKE_KEY not in caplog.text

    def test_key_absent_from_suggest_response(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", self._FAKE_KEY)
        self._mock_anthropic(monkeypatch)
        with caplog.at_level(logging.INFO, logger="framegen"):
            r = client.post(
                "/suggest",
                json={"spec": _FAILING_SPEC, "original_request": "workbench"},
            )
        assert self._FAKE_KEY not in r.text
        assert self._FAKE_KEY not in caplog.text
