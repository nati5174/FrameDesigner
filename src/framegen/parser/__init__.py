from __future__ import annotations

import re as _re
from dataclasses import dataclass, field
from typing import Literal

from framegen.spec import FrameSpec

Outcome = Literal["spec_valid", "spec_invalid", "not_parsed"]
ParserUsed = Literal["rule_based", "llm", "none"]


@dataclass
class ParseResult:
    outcome: Outcome
    spec: FrameSpec | None  # set iff spec_valid
    error: str | None  # set iff spec_invalid; also set on not_parsed when LLM errored
    defaults_applied: list[str] = field(default_factory=list)
    parser_used: ParserUsed = "none"


def parse(text: str) -> ParseResult:
    """Dispatcher: rule-based first, LLM fallback on not_parsed."""
    from framegen.parser.llm import parse as llm_parse
    from framegen.parser.rule_based import parse as rb_parse

    # Pre-checks that apply before either parser
    imperial_error = _check_imperial(text)
    if imperial_error:
        return ParseResult(
            outcome="spec_invalid",
            spec=None,
            error=imperial_error,
            parser_used="none",
        )

    enclosure_error = _check_enclosure(text)
    if enclosure_error:
        return ParseResult(
            outcome="spec_invalid",
            spec=None,
            error=enclosure_error,
            parser_used="none",
        )

    result = rb_parse(text)
    if result.outcome != "not_parsed":
        return result

    return llm_parse(text)


# ── Shared pre-checks ─────────────────────────────────────────────────────────

# Imperial: unit token immediately after a digit (optional space).
# "in" is only a unit when NOT followed by optional whitespace + a letter
# (so "1500 in width" is not imperial but "60 in" / "60in" / "60 inches" is).
_IMPERIAL_RE = _re.compile(
    r'\d\s*(?:'
    r'"|'                           # inch symbol
    r"''|"                          # double apostrophe
    r"inches?(?!\w)|"               # inch / inches
    r"in(?!\s*[a-zA-Z])|"           # bare "in" not followed by a word
    r'ft(?!\w)|'                    # ft
    r"feet(?!\w)|"                  # feet
    r"'(?!\d)"                      # single apostrophe not followed by digit
    r')',
    _re.IGNORECASE,
)

# Enclosure: exact standalone words
_ENCLOSURE_RE = _re.compile(
    r'(?<!\w)(?:enclosure|cabinet|enclosed)(?!\w)',
    _re.IGNORECASE,
)

# "box" standalone — but not "toolbox", "inbox", etc.
_BOX_RE = _re.compile(r'(?<!\w)box(?!\w)', _re.IGNORECASE)


def _check_imperial(text: str) -> str | None:
    if _IMPERIAL_RE.search(text):
        return "Imperial units are not supported. Please use mm, cm, or m."
    return None


def _check_enclosure(text: str) -> str | None:
    if _ENCLOSURE_RE.search(text) or _BOX_RE.search(text):
        return "Enclosures are not supported; only open frames."
    return None
