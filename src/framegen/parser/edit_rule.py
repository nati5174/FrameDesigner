"""
Rule-based edit parser for the /edit endpoint.

Handles common single-field and multi-field edits without an LLM call.

Returns EditRuleResult with outcome:
  "operations"  — one or more edit operations to apply
  "new_design"  — message signals starting a new design
  "not_matched" — rule parser cannot handle this message

Pre-checks (imperial, enclosure) and unsupported keyword detection are the
caller's responsibility.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# ── Types ─────────────────────────────────────────────────────────────────────

OpType = Literal["set", "add", "add_level", "remove_level", "set_level_count"]


@dataclass
class Operation:
    field: str
    op: OpType
    # set/add:            float (mm for dimensions; kg for loads; +/-)
    # set centre_legs:    bool
    # set null:           None  (removes shelf_height_mm)
    # set profile_series: str  (catalog series name, e.g. "40-series")
    # remove_level:        None
    # add_level:           float (height in mm)
    # set_level_count:     float (treated as int)
    value: float | bool | str | None


@dataclass
class EditRuleResult:
    outcome: Literal["operations", "new_design", "clarify", "not_matched"]
    operations: list[Operation] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


# ── Unit conversion ────────────────────────────────────────────────────────────

def _to_mm(value: float, unit: str | None) -> float:
    if unit is None:
        return value
    u = unit.lower()
    if u.startswith("cm"):
        return value * 10.0
    if u == "m" or u.startswith("metre") or u.startswith("meter"):
        return value * 1000.0
    return value  # mm or bare


# ── New-design detection ──────────────────────────────────────────────────────

_NEW_DESIGN_RE = re.compile(
    r'(?<!\w)(?:'
    r'start\s+over'
    r'|start\s+again'
    r'|from\s+scratch'
    r'|new\s+design'
    r'|instead\s+(?:build|make|design|create)'
    r'|completely\s+different'
    r')(?!\w)',
    re.IGNORECASE,
)

# Frame type keyword
_FRAME_TYPE_RE = re.compile(
    r'(?<!\w)(?:'
    r'table|bench|workbench|desk|stand'
    r'|shelf\s+unit|shelving(?:\s+unit)?'
    r'|bookcase|bookshelf'
    r'|rack(?:ing)?'
    r')(?!\w)',
    re.IGNORECASE,
)

# Two numbers separated by × / x / by — indicates both W and D supplied
_DIM_PAIR_RE = re.compile(
    r'\d+(?:\.\d+)?\s*(?:mm|cm|m\b)?'
    r'\s*(?:x|×|by)\s*'
    r'\d+(?:\.\d+)?\s*(?:mm|cm|m\b)?',
    re.IGNORECASE,
)


def _is_new_design(text: str) -> bool:
    """True if the message signals a new design rather than an edit."""
    if _NEW_DESIGN_RE.search(text):
        return True
    # Frame-type word + at least two dimensions together → new design
    if _FRAME_TYPE_RE.search(text) and _DIM_PAIR_RE.search(text):
        return True
    return False


# ── Individual field matchers ─────────────────────────────────────────────────
# Each returns Operation | None.


def _match_height(text: str) -> Operation | None:
    # add: "N mm taller" / "make it N mm taller"
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+taller',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("height_mm", "add", +_to_mm(float(m.group(1)), m.group(2)))

    # add: "taller by N mm"
    m = re.search(r'taller\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?', text, re.IGNORECASE)
    if m:
        return Operation("height_mm", "add", +_to_mm(float(m.group(1)), m.group(2)))

    # add: "N mm shorter" / "make it N mm shorter"
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+shorter',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("height_mm", "add", -_to_mm(float(m.group(1)), m.group(2)))

    # add: "shorter by N mm"
    m = re.search(r'shorter\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?', text, re.IGNORECASE)
    if m:
        return Operation("height_mm", "add", -_to_mm(float(m.group(1)), m.group(2)))

    # set: "make it N mm tall/high" (not 'er')
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+(?:tall|high)(?!er)',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("height_mm", "set", _to_mm(float(m.group(1)), m.group(2)))

    # set: "height to N mm" / "height N mm"
    m = re.search(
        r'height\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("height_mm", "set", _to_mm(float(m.group(1)), m.group(2)))

    # set: "N mm in height"
    m = re.search(
        r'(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+in\s+height',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("height_mm", "set", _to_mm(float(m.group(1)), m.group(2)))

    return None


def _match_width(text: str) -> Operation | None:
    # add: "N mm wider"
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+wider',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("width_mm", "add", +_to_mm(float(m.group(1)), m.group(2)))

    # add: "wider by N mm"
    m = re.search(r'wider\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?', text, re.IGNORECASE)
    if m:
        return Operation("width_mm", "add", +_to_mm(float(m.group(1)), m.group(2)))

    # add: "N mm narrower"
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+narrower',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("width_mm", "add", -_to_mm(float(m.group(1)), m.group(2)))

    # add: "narrower by N mm"
    m = re.search(r'narrower\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?', text, re.IGNORECASE)
    if m:
        return Operation("width_mm", "add", -_to_mm(float(m.group(1)), m.group(2)))

    # set: "make it N mm wide" (not 'r')
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+wide(?!r)',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("width_mm", "set", _to_mm(float(m.group(1)), m.group(2)))

    # set: "width to N mm" / "width N mm"
    m = re.search(
        r'width\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("width_mm", "set", _to_mm(float(m.group(1)), m.group(2)))

    return None


def _match_depth(text: str) -> Operation | None:
    # add: "N mm deeper"
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+deeper',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("depth_mm", "add", +_to_mm(float(m.group(1)), m.group(2)))

    # add: "deeper by N mm"
    m = re.search(r'deeper\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?', text, re.IGNORECASE)
    if m:
        return Operation("depth_mm", "add", +_to_mm(float(m.group(1)), m.group(2)))

    # add: "N mm shallower"
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+shallower',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("depth_mm", "add", -_to_mm(float(m.group(1)), m.group(2)))

    # add: "shallower by N mm"
    m = re.search(r'shallower\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?', text, re.IGNORECASE)
    if m:
        return Operation("depth_mm", "add", -_to_mm(float(m.group(1)), m.group(2)))

    # set: "make it N mm deep" (not 'er')
    m = re.search(
        r'(?:make\s+it\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)\s+deep(?!er)',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("depth_mm", "set", _to_mm(float(m.group(1)), m.group(2)))

    # set: "depth to N mm" / "depth N mm"
    m = re.search(
        r'depth\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("depth_mm", "set", _to_mm(float(m.group(1)), m.group(2)))

    return None


def _match_load(text: str) -> Operation | None:
    # "can it hold N kg" / "holds N kg" / "hold N kg"
    m = re.search(
        r'(?:can\s+it\s+)?holds?\s+(\d+(?:\.\d+)?)\s*(?:kg)?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("target_load_kg", "set", float(m.group(1)))

    # "change/set the load to N kg" / "load to N kg" / "load N kg"
    m = re.search(
        r'(?:(?:change|set)\s+)?(?:the\s+)?load\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(?:kg)?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("target_load_kg", "set", float(m.group(1)))

    # "N kg load" / "N kg capacity"
    m = re.search(
        r'(\d+(?:\.\d+)?)\s*kg\s+(?:load|capacity)',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("target_load_kg", "set", float(m.group(1)))

    # "target load N" / "capacity N kg"
    m = re.search(
        r'(?:target\s+load|capacity)\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:kg)?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("target_load_kg", "set", float(m.group(1)))

    return None


def _match_load_per_level(text: str) -> Operation | None:
    # "N kg per level/shelf/tier"
    m = re.search(
        r'(\d+(?:\.\d+)?)\s*kg\s+per\s+(?:level|shelf|tier)',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("load_per_level_kg", "set", float(m.group(1)))

    # "load per level/shelf/tier to N kg"
    m = re.search(
        r'load\s+per\s+(?:level|shelf|tier)\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(?:kg)?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("load_per_level_kg", "set", float(m.group(1)))

    return None


def _match_shelf(text: str) -> Operation | None:
    # remove (check first)
    if re.search(
        r'(?:remove\s+(?:the\s+)?shelf|no\s+shelf|without\s+(?:a\s+)?shelf)',
        text, re.IGNORECASE,
    ):
        return Operation("shelf_height_mm", "set", None)

    # raise by N
    m = re.search(
        r'raise\s+(?:the\s+)?shelf\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        v = +_to_mm(float(m.group(1)), m.group(2))
        return Operation("shelf_height_mm", "add", v)

    # raise to N
    m = re.search(
        r'raise\s+(?:the\s+)?shelf\s+to\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        v = _to_mm(float(m.group(1)), m.group(2))
        return Operation("shelf_height_mm", "set", v)

    # lower by N
    m = re.search(
        r'lower\s+(?:the\s+)?shelf\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        v = -_to_mm(float(m.group(1)), m.group(2))
        return Operation("shelf_height_mm", "add", v)

    # lower to N
    m = re.search(
        r'lower\s+(?:the\s+)?shelf\s+to\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        v = _to_mm(float(m.group(1)), m.group(2))
        return Operation("shelf_height_mm", "set", v)

    # add with height: "add a shelf at N mm"
    m = re.search(
        r'add\s+(?:a\s+)?shelf\s+at\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        v = _to_mm(float(m.group(1)), m.group(2))
        return Operation("shelf_height_mm", "set", v)

    # add without height: "add a shelf" (default 300 mm); guard against "shelf unit"
    if re.search(r'add\s+(?:a\s+)?shelf(?!\s+unit)', text, re.IGNORECASE):
        return Operation("shelf_height_mm", "set", 300.0)

    # shelf at / shelf height N
    m = re.search(
        r'shelf\s+(?:at|height)\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        v = _to_mm(float(m.group(1)), m.group(2))
        return Operation("shelf_height_mm", "set", v)

    return None


def _match_centre_legs(text: str) -> Operation | None:
    # removal patterns (check before add to avoid "centre legs" substring match)
    if re.search(
        r'(?:remove|no|without)\s+(?:centre|center|middle)\s+legs?',
        text, re.IGNORECASE,
    ):
        return Operation("centre_legs", "set", False)
    if re.search(
        r'(?:remove|no|without)\s+middle\s+support',
        text, re.IGNORECASE,
    ):
        return Operation("centre_legs", "set", False)

    # add patterns
    if re.search(
        r'(?:add\s+)?(?:centre|center|middle)\s+legs?',
        text, re.IGNORECASE,
    ):
        return Operation("centre_legs", "set", True)
    if re.search(
        r'(?:add\s+)?middle\s+support',
        text, re.IGNORECASE,
    ):
        return Operation("centre_legs", "set", True)

    return None


def _match_level_add(text: str) -> Operation | None:
    # "add a level at N mm" — height in mm required
    m = re.search(
        r'add\s+(?:a\s+|(?:an?\s+)?new\s+)?level\s+at\s+(\d+(?:\.\d+)?)\s*(mm|cm|m)?',
        text, re.IGNORECASE,
    )
    if m:
        val = _to_mm(float(m.group(1)), m.group(2))
        return Operation("level_heights_mm", "add_level", val)

    return None


def _match_level_remove(text: str) -> Operation | None:
    if re.search(
        r'remove\s+(?:a\s+|the\s+)?(?:top\s+|last\s+|one\s+)?level',
        text, re.IGNORECASE,
    ):
        return Operation("level_heights_mm", "remove_level", None)
    return None


def _match_level_count(text: str) -> Operation | None:
    # "N levels" / "set to N levels" / "change to N levels"
    m = re.search(
        r'(?:set\s+(?:it\s+)?to\s+|change\s+to\s+)?(\d+)\s+levels?',
        text, re.IGNORECASE,
    )
    if m:
        return Operation("level_heights_mm", "set_level_count", float(int(m.group(1))))
    return None


# ── Block pattern (W × D [× H]) ───────────────────────────────────────────────

_BLOCK_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(mm|cm|m\b)?'
    r'\s*(?:x|×|by)\s*'
    r'(\d+(?:\.\d+)?)\s*(mm|cm|m\b)?'
    r'(?:\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*(mm|cm|m\b)?)?',
    re.IGNORECASE,
)


def _match_block(text: str) -> list[Operation]:
    """
    Detect 'N × M' or 'N × M × H' and return set operations for W/D/H.
    Returns empty list if no block is found or units are ambiguous.
    """
    m = _BLOCK_RE.search(text)
    if not m:
        return []

    raw: list[tuple[float, str | None]] = [
        (float(m.group(1)), m.group(2)),
        (float(m.group(3)), m.group(4)),
    ]
    if m.group(5):
        raw.append((float(m.group(5)), m.group(6)))

    # Trailing-unit propagation: if last value has a unit and others don't, apply it
    last_unit = raw[-1][1]
    if last_unit and all(v[1] is None for v in raw[:-1]):
        raw = [(v[0], last_unit) for v in raw]

    # Unitless-small guard: bare number < 100 is ambiguous (mm? cm? m?)
    for val, unit in raw:
        if unit is None and val < 100:
            return []

    ops: list[Operation] = [
        Operation("width_mm", "set", _to_mm(raw[0][0], raw[0][1])),
        Operation("depth_mm", "set", _to_mm(raw[1][0], raw[1][1])),
    ]
    if len(raw) > 2:
        ops.append(Operation("height_mm", "set", _to_mm(raw[2][0], raw[2][1])))
    return ops


# ── Profile series matcher ────────────────────────────────────────────────────

# Map of pattern → canonical series name. Part numbers (2020/3030/4040/4545)
# and explicit series names are all recognised.
def _profile_pat(n: str) -> re.Pattern[str]:
    nn = n * 2  # "20" → "2020"
    return re.compile(
        rf'(?<!\d){n}\s*-?\s*series'            # "30-series" or "30 series"
        rf'|(?<!\d){n}\s*mm?\s+(?:profile|extrusion|series)'  # "30mm profile"
        rf'|(?<!\d){n}\s*mm?(?!\d)(?=\s*$|\s*[,.])'  # "45mm" at end/punctuation
        rf'|(?<!\d){nn}(?!\d)',                 # "3030"
        re.IGNORECASE,
    )


_PROFILE_MAP: list[tuple[re.Pattern[str], str]] = [
    (_profile_pat("20"), "20-series"),
    (_profile_pat("30"), "30-series"),
    (_profile_pat("40"), "40-series"),
    (_profile_pat("45"), "45-series"),
]


def _match_profile_series(text: str) -> Operation | None:
    """Detect profile series requests, e.g. 'use 30 series', '4040'."""
    # Only match when preceded by an intent verb or when part number / series label
    # is the subject of the request.
    intent = re.compile(
        r'(?:use|switch\s+to|change\s+(?:the\s+)?(?:profile|series)\s+to'
        r'|upgrade\s+to|downgrade\s+to)',
        re.IGNORECASE,
    )
    for pattern, series in _PROFILE_MAP:
        m = pattern.search(text)
        if not m:
            continue
        # Accept if preceded by an intent verb, or if the bare part-number /
        # series name appears at the start of the text (e.g. "45-series please")
        start = m.start()
        preceding = text[:start]
        if intent.search(preceding) or start < 10:
            return Operation("profile_series", "set", series)
    return None


# ── Direction-only detection (no number → clarify) ────────────────────────────
# Patterns that express intent but give no amount. Checked only when no
# numbered matchers fired. Each tuple is (field_name, compiled_pattern).

_DIRECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # height
    ("height_mm", re.compile(
        r'(?:make\s+it\s+)?taller(?!\s+by\s+\d)(?!\s+\d)',
        re.IGNORECASE,
    )),
    ("height_mm", re.compile(
        r'(?:make\s+it\s+)?shorter(?!\s+by\s+\d)(?!\s+\d)',
        re.IGNORECASE,
    )),
    # width
    ("width_mm", re.compile(
        r'(?:make\s+it\s+)?wider(?!\s+by\s+\d)(?!\s+\d)',
        re.IGNORECASE,
    )),
    ("width_mm", re.compile(
        r'(?:make\s+it\s+)?narrower(?!\s+by\s+\d)(?!\s+\d)',
        re.IGNORECASE,
    )),
    # depth
    ("depth_mm", re.compile(
        r'(?:make\s+it\s+)?deeper(?!\s+by\s+\d)(?!\s+\d)',
        re.IGNORECASE,
    )),
    ("depth_mm", re.compile(
        r'(?:make\s+it\s+)?shallower(?!\s+by\s+\d)(?!\s+\d)',
        re.IGNORECASE,
    )),
    # load / capacity
    ("target_load_kg", re.compile(
        r'more\s+(?:load|capacity|weight)',
        re.IGNORECASE,
    )),
    ("target_load_kg", re.compile(
        r'(?:increase|improve|boost)\s+(?:the\s+)?(?:load|capacity|weight)',
        re.IGNORECASE,
    )),
    ("target_load_kg", re.compile(
        r'(?:higher|heavier)\s+(?:load|capacity|weight)',
        re.IGNORECASE,
    )),
]


def _clarify_fields(text: str) -> list[str]:
    """
    Return a deduplicated list of field names whose direction was stated
    but no amount given. Returns [] if nothing recognisable was found.
    """
    seen: set[str] = set()
    fields: list[str] = []
    for fld, pat in _DIRECTION_PATTERNS:
        if fld not in seen and pat.search(text):
            seen.add(fld)
            fields.append(fld)
    return fields


# ── Main parse function ───────────────────────────────────────────────────────

_SINGLE_MATCHERS = [
    _match_height,
    _match_width,
    _match_depth,
    _match_load,
    _match_load_per_level,
    _match_shelf,
    _match_centre_legs,
    _match_level_add,
    _match_level_remove,
    _match_level_count,
    _match_profile_series,
]


def parse_edit(text: str) -> EditRuleResult:
    """
    Try to parse `text` as an edit to an existing design.

    Returns:
      "new_design"  if the text explicitly requests a new design.
      "operations"  if one or more edit operations were recognised.
      "not_matched" if the rule parser cannot handle the text.
    """
    if _is_new_design(text):
        return EditRuleResult(outcome="new_design")

    ops: list[Operation] = []
    used_fields: set[str] = set()

    for matcher in _SINGLE_MATCHERS:
        op = matcher(text)
        if op is None:
            continue
        if op.field in used_fields:
            # Two matchers fired on the same field — ambiguous
            return EditRuleResult(outcome="not_matched")
        used_fields.add(op.field)
        ops.append(op)

    # Block pattern for W/D/H if not already assigned by individual matchers
    if "width_mm" not in used_fields and "depth_mm" not in used_fields:
        block_ops = _match_block(text)
        for op in block_ops:
            if op.field in used_fields:
                return EditRuleResult(outcome="not_matched")
            used_fields.add(op.field)
            ops.append(op)

    if ops:
        return EditRuleResult(outcome="operations", operations=ops)

    # Direction word present but no amount given → ask for the missing value
    missing = _clarify_fields(text)
    if missing:
        return EditRuleResult(outcome="clarify", missing=missing)

    return EditRuleResult(outcome="not_matched")
