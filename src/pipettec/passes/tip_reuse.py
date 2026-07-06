"""Tip-reuse pass — the flagship tip-saving optimization.

Prior art (cited, not claimed as novel)
----------------------------------------
Minimizing disposable tips in liquid handling is a solved operations-research problem. This
pass *applies* that published formulation, in which liquid transfers are modelled as a
capacitated vehicle-routing / linear-programming problem and tips are the scarce resource:

* Kanigowska et al., "Smart DNA Fabrication Using Sound Waves...", and the tip-minimization
  formulation surveyed in *NAR Genomics & Bioinformatics* 4(2), 2022 (PMC9074407).
* "Minimizing tip usage in liquid handling", *Digital Discovery*, 2025 (arXiv:2506.02795).

We claim engineering/packaging, not algorithmic novelty.

What this pass does
-------------------
Within one tip class, a single tip may serve many transfers *without a wash* only when doing so
cannot cross-contaminate. The safe, standard case (and the one the literature exploits for the
biggest win) is **one clean reagent distributed from a single source**: consecutive transfers
that share the same ``source`` and ``tip_class`` can reuse one tip, because nothing new enters
the tip between dispenses.

Concretely: we scan transfers in order and merge a maximal run that shares
``(instrument, tip_class, source)`` into one ``tip_group``. Each such run collapses N tips into
1. Delivery-equivalence is preserved exactly (we never change any ``(source, dest, volume)``);
we only annotate tip lifetime.
"""

from __future__ import annotations

from dataclasses import replace

from pipettec.ir import Transfer, TransferGraph


def tip_reuse(graph: TransferGraph) -> TransferGraph:
    """Merge maximal same-source, same-tip-class runs into shared tip groups."""
    out = graph.copy()
    new_transfers: list[Transfer] = []
    next_group = _max_group(out) + 1

    i = 0
    ts = out.transfers
    n = len(ts)
    while i < n:
        t = ts[i]
        # Only merge single-channel, not-yet-grouped transfers.
        if t.channel_group is not None or t.tip_group is not None:
            new_transfers.append(t)
            i += 1
            continue
        # Extend a run sharing (instrument, tip_class, source).
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
