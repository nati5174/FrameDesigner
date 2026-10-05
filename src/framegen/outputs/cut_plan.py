from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from framegen.generate import Bar

# Maximum nodes the branch-and-bound search will explore before giving up.
# Worst-case work at this limit: O(100_000 x 60) ~= 6M operations, well under
# 1 second in Python. Typical frames (20-30 pieces) finish in far fewer nodes.
_NODE_LIMIT: int = 100_000


@dataclass(frozen=True)
class CutPlanPiece:
    length_mm: float
    label: str  # bar role, e.g. "leg", "top_rail_width"


@dataclass(frozen=True)
class StockBarPlan:
    pieces: tuple[CutPlanPiece, ...]
    used_mm: float    # sum of (length + kerf) for each piece
    offcut_mm: float  # stock_length_mm - used_mm


@dataclass(frozen=True)
class ProfileCutPlan:
    profile_id: str
    stock_bars: tuple[StockBarPlan, ...]
    does_not_fit: tuple[CutPlanPiece, ...]  # pieces longer than stock_length_mm
    total_stock_bars: int
    total_offcut_mm: float
    waste_pct: float   # 100 × total_offcut / (total_stock_bars × stock_length_mm)
    lower_bound_bars: int
    is_optimal: bool   # True when plan is proved optimal


@dataclass(frozen=True)
class CutPlanResult:
    profiles: tuple[ProfileCutPlan, ...]
    stock_length_mm: float
    kerf_mm: float


# ── First-fit decreasing ───────────────────────────────────────────────────────

def _ffd(sizes: list[float], capacity: float) -> list[list[int]]:
    """
    First-fit decreasing bin packing.

    sizes must be sorted descending.  Each element is the effective size of a
    piece (already length + kerf).  Returns a list of bins; each bin is a list
    of piece indices into sizes.
    """
    bins_rem: list[float] = []
    bins_cont: list[list[int]] = []
    for i, s in enumerate(sizes):
        placed = False
        for j, rem in enumerate(bins_rem):
            if rem >= s - 1e-9:
                bins_cont[j].append(i)
                bins_rem[j] -= s
                placed = True
                break
        if not placed:
            bins_cont.append([i])
            bins_rem.append(capacity - s)
    return bins_cont


# ── Branch-and-bound ──────────────────────────────────────────────────────────

def _b_and_b(
    sizes: list[float],
    capacity: float,
    ffd_bins: list[list[int]],
    node_limit: int,
) -> tuple[list[list[int]], bool]:
    """
    Bounded depth-first branch-and-bound bin packing.

    sizes must be sorted descending; each element is (length + kerf).
    ffd_bins is the initial best solution used to seed the upper bound.
    Returns (best_bins, exhausted).  exhausted=True means the search proved
    the returned solution is optimal.

    Symmetry pruning: at each step, bins with the same remaining capacity are
    treated as equivalent and only the first is tried.
    Upper-bound pruning: opening a new bin is skipped when doing so cannot
    produce a solution strictly better than the current best.
    """
    n = len(sizes)
    best: list[list[list[int]]] = [[list(b) for b in ffd_bins]]
    nodes: list[int] = [0]
    exhausted: list[bool] = [True]

    def search(
        idx: int,
        bins_rem: list[float],
        bins_cont: list[list[int]],
    ) -> None:
        nodes[0] += 1
        if nodes[0] > node_limit:
            exhausted[0] = False
            return

        if idx == n:
            if len(bins_cont) < len(best[0]):
                best[0] = [list(b) for b in bins_cont]
            return

        size = sizes[idx]
        seen_rem: set[float] = set()

        for j in range(len(bins_cont)):
            rem = bins_rem[j]
            # Symmetry: skip bins with the same remaining capacity as one we
            # already tried at this level.
            rem_key = round(rem, 9)
            if rem_key in seen_rem:
                continue
            if rem >= size - 1e-9:
                seen_rem.add(rem_key)
                bins_rem[j] -= size
                bins_cont[j].append(idx)
                search(idx + 1, bins_rem, bins_cont)
                bins_rem[j] += size
                bins_cont[j].pop()
                if nodes[0] > node_limit:
                    return

        # Open a new bin only if the result can still beat the current best.
        if len(bins_cont) + 1 < len(best[0]):
            bins_rem.append(capacity - size)
            bins_cont.append([idx])
            search(idx + 1, bins_rem, bins_cont)
            bins_rem.pop()
            bins_cont.pop()

    search(0, [], [])
    return best[0], exhausted[0]


# ── Public API ────────────────────────────────────────────────────────────────

def plan_cuts(
    bars: list[Bar],
    stock_length_mm: float,
    kerf_mm: float,
    _node_limit: int = _NODE_LIMIT,
) -> CutPlanResult:
    """
    Compute a stock-bar cut plan for a list of bars.

    Convention: each piece occupies (length + kerf) mm on a stock bar.
    This is stated on the page wherever the plan is shown.

    Algorithm: first-fit decreasing (FFD) per profile, followed by a bounded
    branch-and-bound post-pass when FFD exceeds the lower bound.

    Raises ValueError for out-of-range stock_length_mm or kerf_mm.
    """
    if not (500.0 <= stock_length_mm <= 8000.0):
        raise ValueError(
            f"stock_length_mm must be 500–8000, got {stock_length_mm}"
        )
    if not (0.0 <= kerf_mm <= 10.0):
        raise ValueError(f"kerf_mm must be 0–10, got {kerf_mm}")

    groups: dict[str, list[Bar]] = defaultdict(list)
    for bar in bars:
        groups[bar.profile_id].append(bar)

    profiles: list[ProfileCutPlan] = []

    for profile_id in sorted(groups):
        profile_bars = groups[profile_id]
        pieces_all = [CutPlanPiece(b.length_mm, b.role) for b in profile_bars]
        fits = [p for p in pieces_all if p.length_mm <= stock_length_mm]
        does_not_fit = tuple(p for p in pieces_all if p.length_mm > stock_length_mm)

        if not fits:
            profiles.append(ProfileCutPlan(
                profile_id=profile_id,
                stock_bars=(),
                does_not_fit=does_not_fit,
                total_stock_bars=0,
                total_offcut_mm=0.0,
                waste_pct=0.0,
                lower_bound_bars=0,
                is_optimal=True,
            ))
            continue

        fits_sorted = sorted(fits, key=lambda p: p.length_mm, reverse=True)
        sizes = [p.length_mm + kerf_mm for p in fits_sorted]

        total_used = sum(sizes)
        lower_bound = math.ceil(total_used / stock_length_mm)

        ffd_result = _ffd(sizes, stock_length_mm)

        if len(ffd_result) == lower_bound:
            final_bins = ffd_result
            is_optimal = True
        else:
            final_bins, exhausted = _b_and_b(
                sizes, stock_length_mm, ffd_result, _node_limit
            )
            is_optimal = exhausted or (len(final_bins) == lower_bound)

        stock_bars: list[StockBarPlan] = []
        for bin_indices in final_bins:
            bin_pieces = tuple(fits_sorted[i] for i in bin_indices)
            used = sum(p.length_mm + kerf_mm for p in bin_pieces)
            offcut = stock_length_mm - used
            stock_bars.append(StockBarPlan(
                pieces=bin_pieces,
                used_mm=round(used, 6),
                offcut_mm=round(offcut, 6),
            ))

        total_offcut = sum(b.offcut_mm for b in stock_bars)
        total_bars = len(stock_bars)
        waste_pct = (
            round(100.0 * total_offcut / (total_bars * stock_length_mm), 4)
            if total_bars > 0
            else 0.0
        )

        profiles.append(ProfileCutPlan(
            profile_id=profile_id,
            stock_bars=tuple(stock_bars),
            does_not_fit=does_not_fit,
            total_stock_bars=total_bars,
            total_offcut_mm=round(total_offcut, 6),
            waste_pct=waste_pct,
            lower_bound_bars=lower_bound,
            is_optimal=is_optimal,
        ))

    return CutPlanResult(
        profiles=tuple(profiles),
        stock_length_mm=stock_length_mm,
        kerf_mm=kerf_mm,
    )
