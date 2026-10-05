"""Shared fixtures for the test suite."""
from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _reset_state() -> Generator[None, None, None]:
    """
    Reset the daily SDK-call counter and slowapi in-memory limiter state
    before every test so tests are independent of execution order.
    """
    from framegen import _llm_counter
    from framegen.api import limiter

    _llm_counter.reset()

    # Clear slowapi's in-memory rate-limit storage.
    # slowapi delegates to the `limits` library's MemoryStorage whose
    # internal dict is accessible via the `storage` attribute.
    storage = limiter._storage  # type: ignore[attr-defined]
    for attr in ("storage", "_storage", "_events"):
        d = getattr(storage, attr, None)
        if isinstance(d, dict):
            d.clear()
            break

    yield

    _llm_counter.reset()
