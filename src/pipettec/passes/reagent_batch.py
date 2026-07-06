"""Reagent-batching (distribute) pass.

One aspirate can feed many dispenses when a single clean reagent is distributed from one source
to many destinations. This pass recognises same-source, same-tip-class runs and marks them as a
shared tip group — the "distribute" pattern — so codegen picks up one tip for the whole batch.

This overlaps with :mod:`tip_reuse` (both exploit a shared clean source); it exists as a
distinct pass so its contribution is *independently benchmarkable*, per the PRD requirement that
each pass reports its own delta. It is idempotent with respect to tip_reuse: transfers already
tip-grouped are left untouched, so running both never double-counts.

Correctness: identical to tip_reuse — only tip lifetime is annotated, no delivery changes.
"""

from __future__ import annotations

from dataclasses import replace

from pipettec.ir import Transfer, TransferGraph


def reagent_batch(graph: TransferGraph) -> TransferGraph:
    """Group any remaining same-source, same-tip-class runs (the distribute pattern)."""
    out = graph.copy()
    ts = out.transfers
    n = len(ts)
    next_group = _max_group(out) + 1
    new_transfers: list[Transfer] = []

    i = 0
    while i < n:
        t = ts[i]
        if t.channel_group is not None or t.tip_group is not None:
            new_transfers.append(t)
            i += 1
            continue
        j = i + 1
        while (
            j < n
            and ts[j].channel_group is None
            and ts[j].tip_group is None
            and ts[j].instrument == t.instrument
            and ts[j].tip_class == t.tip_class
            and ts[j].source == t.source
        ):
            j += 1
        run = ts[i:j]
        if len(run) > 1:
            gid = next_group
            next_group += 1
            for r in run:
                new_transfers.append(replace(r, tip_group=gid))
        else:
            new_transfers.append(t)
        i = j

    out.transfers = new_transfers
    return out


def _max_group(graph: TransferGraph) -> int:
    groups = [t.tip_group for t in graph.transfers if t.tip_group is not None]
    return max(groups) if groups else -1
