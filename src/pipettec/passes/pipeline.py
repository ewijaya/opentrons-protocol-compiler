"""The optimization pipeline: run passes in a fixed, dependency-respecting order.

Order matters:

1. ``multichannel_pack`` first — collapse full columns into 8-channel moves before any
   single-channel tip grouping claims those transfers.
2. ``source_reorder`` — cluster remaining single-channel transfers by source so runs are
   adjacent (dependency-safe; never moves an aspirate before its fill).
3. ``tip_reuse`` — merge adjacent same-source runs into shared tips.
4. ``reagent_batch`` — catch any remaining distributable runs.

"Naive mode" is simply this pipeline with zero passes: the same front-end and codegen, so the
before/after benchmark is apples-to-apples from one IR (see PROJECT.md).
"""

from __future__ import annotations

from collections.abc import Callable

from pipettec.ir import TransferGraph
from pipettec.passes.multichannel_pack import multichannel_pack
from pipettec.passes.reagent_batch import reagent_batch
from pipettec.passes.source_reorder import source_reorder
from pipettec.passes.tip_reuse import tip_reuse

Pass = Callable[[TransferGraph], TransferGraph]

DEFAULT_PIPELINE: tuple[Pass, ...] = (
    multichannel_pack,
    source_reorder,
    tip_reuse,
    reagent_batch,
)


def optimize(
    graph: TransferGraph, passes: tuple[Pass, ...] = DEFAULT_PIPELINE
) -> TransferGraph:
    """Run the pass pipeline and return the optimized graph (marks ``optimized=True``)."""
    g = graph
    for p in passes:
        g = p(g)
    g.optimized = True
    return g
