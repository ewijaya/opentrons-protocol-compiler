"""Metrics and the before/after benchmark table.

Tips and steps are **exact** counts read off the IR. The wall-clock figure is a transparent
*model estimate* (per-operation time constants), clearly labelled as such — never presented as a
hardware measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipettec.ir import TransferGraph

# Transparent time-model constants (seconds). These are order-of-magnitude estimates for an OT-2
# and are used only for the *estimated* wall-clock line; tips and steps are exact.
_T_TIP_CHANGE = 8.0  # pick up + drop
_T_ASPIRATE = 3.0
_T_DISPENSE = 3.0
_T_MOVE = 2.0  # inter-well travel per operation


@dataclass(frozen=True)
class Metrics:
    """Exact resource counts (tips, steps, aspirations) + an estimated wall-clock."""

    tips: int
    aspirations: int
    dispenses: int
    steps: int
    total_volume_ul: float
    est_seconds: float

    @property
    def est_minutes(self) -> float:
        return round(self.est_seconds / 60.0, 1)


def _logical_ops(graph: TransferGraph) -> int:
    """Number of emitted aspirate/dispense pairs (channel groups count once)."""
    seen_cg: set[int] = set()
    ops = 0
    for t in graph.transfers:
        if t.channel_group is not None:
            if t.channel_group in seen_cg:
                continue
            seen_cg.add(t.channel_group)
        ops += 1
    return ops


def compute_metrics(graph: TransferGraph) -> Metrics:
    """Compute exact counts and the estimated wall-clock for ``graph``."""
    tips = graph.tip_count()
    ops = _logical_ops(graph)
    total_vol = round(sum(t.volume for t in graph.transfers), 3)
    est = tips * _T_TIP_CHANGE + ops * (_T_ASPIRATE + _T_DISPENSE + _T_MOVE)
    return Metrics(
        tips=tips,
        aspirations=ops,
        dispenses=ops,
        steps=ops,
        total_volume_ul=total_vol,
        est_seconds=round(est, 1),
    )


def format_report(graph: TransferGraph, title: str = "PipetteC report") -> str:
    """A human-readable single-graph resource report."""
    m = compute_metrics(graph)
    lines = [
        f"# {title}",
        "",
        f"- transfers (logical ops): {m.steps}",
        f"- tips consumed:           {m.tips}",
        f"- total volume:            {m.total_volume_ul} uL",
        f"- estimated wall-clock:    ~{m.est_minutes} min  (model estimate, not hardware)",
    ]
    return "\n".join(lines)


def format_comparison_markdown(naive: TransferGraph, optimized: TransferGraph) -> str:
    """Markdown before/after table computed from one IR (naive vs optimized)."""
    n = compute_metrics(naive)
    o = compute_metrics(optimized)

    def pct(a: int, b: int) -> str:
        if a == 0:
            return "0%"
        return f"-{round((a - b) / a * 100)}%"

    rows = [
        "| Metric | Naive | Optimized | Reduction |",
        "| --- | ---: | ---: | ---: |",
        f"| Tips | {n.tips} | {o.tips} | {pct(n.tips, o.tips)} |",
        f"| Steps (asp/disp) | {n.steps} | {o.steps} | {pct(n.steps, o.steps)} |",
        f"| Est. time (min) | {n.est_minutes} | {o.est_minutes} | {pct(int(n.est_seconds), int(o.est_seconds))} |",
    ]
    return "\n".join(rows)


def tip_reduction_pct(naive: TransferGraph, optimized: TransferGraph) -> float:
    """Percent tip reduction (optimized vs naive)."""
    n = naive.tip_count()
    o = optimized.tip_count()
    if n == 0:
        return 0.0
    return round((n - o) / n * 100.0, 1)
