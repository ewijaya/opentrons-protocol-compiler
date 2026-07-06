"""Multi-channel packing pass.

Collapses 8 aligned single-channel transfers into one 8-channel move. On a 96- or 384-well
plate an 8-channel pipette addresses a whole column at once, so 8 transfers that
(a) use an 8-channel instrument, (b) share the same source column and dest column, (c) cover all
8 rows ``A..H`` of that column, and (d) share volume and tip class — become a single physical
operation using one column of tips.

This is the packing half of the cited tip-minimization work: multi-channel moves are the
highest-leverage way to reduce both tip pickups and step count on plate-to-plate transfers.

Correctness
-----------
The collapsed group delivers exactly the same ``(source, dest, volume)`` for each of its 8
member transfers — we do not change any delivery, only tag the 8 members with a shared
``channel_group`` and let codegen emit one multi-channel op. Delivery-equivalence holds by
construction (the members are unchanged; :meth:`TransferGraph.delivery_map` sums them the same).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from pipettec.ir import TransferGraph
from pipettec.labware_defs import LABWARE

_ROWS = "ABCDEFGH"


def multichannel_pack(graph: TransferGraph) -> TransferGraph:
    """Tag full-column, 8-row transfer sets on multi-channel pipettes as channel groups."""
    out = graph.copy()
    multi_insts = {i.id for i in out.instruments if i.channels == 8}
    if not multi_insts:
        return out

    # Only pack transfers that are still ungrouped and on a multi pipette.
    def col_of(well: str) -> str:
        return well[1:]

    def row_of(well: str) -> str:
        return well[0]

    def plate_is_8row(lid: str) -> bool:
        lw = out.labware_by_id(lid)
        return LABWARE[lw.load_name].n_rows == 8

    # Group candidate transfers by (instrument, src_labware, src_col, dst_labware, dst_col,
    # volume, tip_class). A full set of 8 distinct rows A..H becomes a channel group.
    buckets: dict[tuple, list[int]] = defaultdict(list)
    for idx, t in enumerate(out.transfers):
        if t.instrument not in multi_insts or t.channel_group is not None or t.tip_group is not None:
            continue
        if not (plate_is_8row(t.source_labware) and plate_is_8row(t.dest_labware)):
            continue
        if row_of(t.source_well) != row_of(t.dest_well):
            continue  # require aligned rows for a straight column move
        key = (
            t.instrument,
            t.source_labware,
            col_of(t.source_well),
            t.dest_labware,
            col_of(t.dest_well),
            round(t.volume, 6),
            t.tip_class,
        )
        buckets[key].append(idx)

    next_cg = _max_channel_group(out) + 1
    assigned: dict[int, int] = {}
    for idxs in buckets.values():
        rows = {row_of(out.transfers[i].source_well) for i in idxs}
        if rows == set(_ROWS):
            cg = next_cg
            next_cg += 1
            for i in idxs:
                assigned[i] = cg

    if not assigned:
        return out

    new_transfers = [
        replace(t, channel_group=assigned[idx]) if idx in assigned else t
        for idx, t in enumerate(out.transfers)
    ]
    out.transfers = new_transfers
    return out


def _max_channel_group(graph: TransferGraph) -> int:
    cgs = [t.channel_group for t in graph.transfers if t.channel_group is not None]
    return max(cgs) if cgs else -1
