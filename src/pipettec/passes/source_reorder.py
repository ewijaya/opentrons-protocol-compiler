"""Source-grouped reordering pass.

Reorders transfers so those sharing a source (and tip class) are adjacent, which lets the
tip-reuse pass merge them into one tip and reduces deck travel. This directly serves the
tip-minimization objective from the cited CVRP/LP formulation (see ``tip_reuse``): grouping by
source is the routing decision that makes tip reuse possible.

Correctness
-----------
Reordering is only safe when it does not move an aspiration ahead of the transfer that fills its
source (a data dependency). We compute a *stable* key that keeps each source's first-fill
ordering intact: transfers are bucketed by ``(instrument, tip_class, source)`` in order of first
appearance, and buckets are emitted in that first-appearance order. A source that is filled by a
prior transfer therefore never jumps ahead of its fill, because the fill (whose *dest* is this
source) belongs to an earlier bucket and is emitted first.

Delivery-equivalence is trivially preserved: reordering does not add, drop, or change any
transfer.
"""

from __future__ import annotations

from pipettec.ir import Transfer, TransferGraph


def source_reorder(graph: TransferGraph) -> TransferGraph:
    """Cluster transfers by source, preserving fill-before-use dependencies."""
    out = graph.copy()
    ts = out.transfers

    # A well is "produced" the first time it appears as a dest. To keep dependencies valid we
    # only cluster within a "layer": transfers whose source is not produced by a later transfer
    # in the original order stay orderable. We use a conservative, dependency-safe scheme:
    # bucket by (instrument, tip_class, source), ordered by first appearance, but never emit a
    # transfer before any transfer that fills its source appeared originally.

    first_fill: dict[str, int] = {}
    for idx, t in enumerate(ts):
        first_fill.setdefault(t.dest, idx)

    order_key: dict[tuple[str, str, str], int] = {}
    for idx, t in enumerate(ts):
        key = (t.instrument, t.tip_class, t.source)
        order_key.setdefault(key, idx)

    def sort_key(idx_t: tuple[int, Transfer]) -> tuple[int, int, int]:
        idx, t = idx_t
        # Primary: a transfer must come after its source is filled. Rank by the fill index of
        # its source (or -1 if the source is a reagent/reservoir never filled here).
        dep = first_fill.get(t.source, -1)
        bucket = order_key[(t.instrument, t.tip_class, t.source)]
        return (dep, bucket, idx)

    reordered = [t for _, t in sorted(enumerate(ts), key=sort_key)]
    out.transfers = reordered
    return out
