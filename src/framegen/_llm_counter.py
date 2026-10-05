"""
Daily SDK-call counter.

Incremented before every client.messages.create() call. When the count
reaches DAILY_CAP, DailyCapReached is raised and the caller falls back to
the rule-based path. The counter resets on process restart (soft cap).
The hard backstop is a spending limit set in the Anthropic Console.
"""
from __future__ import annotations

import threading

DAILY_CAP: int = 200
CAP_NOTE: str = "Daily AI limit reached; using the basic parser"

_lock = threading.Lock()
_calls: int = 0


class DailyCapReached(Exception):
    """Raised by check_and_increment() when the daily cap is hit."""


def check_and_increment() -> None:
    """Increment the counter or raise DailyCapReached if at the cap."""
    global _calls
    with _lock:
        if _calls >= DAILY_CAP:
            raise DailyCapReached
        _calls += 1


def cap_reached() -> bool:
    """Return True if the daily cap has been reached."""
    with _lock:
        return _calls >= DAILY_CAP


def get_count() -> int:
    """Return the current call count (for testing)."""
    with _lock:
        return _calls


def reset() -> None:
    """Reset the counter to zero. For use in tests and at midnight."""
    global _calls
    with _lock:
        _calls = 0
