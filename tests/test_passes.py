"""Unit tests for each optimization pass: reduces its metric AND preserves the invariant.

The invariant (see PROJECT.md § correctness): every pass must preserve the delivery map
(same total volume per (source, dest) pair) and never merge tips across tip classes.
"""

from __future__ import annotations

from pipettec.ir import Instrument, Labware, TipClass, Transfer, TransferGraph
from pipettec.passes import (
    multichannel_pack,
    optimize,
    reagent_batch,
    source_reorder,
    tip_reuse,
)


def distribute_graph(n: int = 8) -> TransferGraph:
    """One clean reagent distributed from reservoir A1 to n plate wells (tip-reusable)."""
    g = TransferGraph()
    g.labware = [
        Labware("plate", "corning_96_wellplate_360ul_flat", "1"),
        Labware("reagents", "nest_12_reservoir_15ml", "2"),
        Labware("tips", "opentrons_96_tiprack_300ul", "3"),
    ]
    g.instruments = [Instrument("p300", "p300_single_gen2", "right", ("tips",))]
    g.tip_classes = [TipClass("diluent")]
    wells = [f"{r}1" for r in "ABCDEFGH"][:n]
    g.transfers = [Transfer("reagents:A1", f"plate:{w}", 50, "p300", "diluent") for w in wells]
    return g


def column_graph() -> TransferGraph:
    """A full 8-row column move on a multi pipette (multichannel-packable)."""
    g = TransferGraph()
    g.labware = [
        Labware("src", "corning_96_wellplate_360ul_flat", "1"),
        Labware("dst", "corning_96_wellplate_360ul_flat", "2"),
        Labware("tips", "opentrons_96_tiprack_300ul", "3"),
    ]
    g.instruments = [Instrument("m", "p300_multi_gen2", "left", ("tips",), channels=8)]
    g.tip_classes = [TipClass("move")]
    g.transfers = [Transfer(f"src:{r}1", f"dst:{r}2", 50, "m", "move") for r in "ABCDEFGH"]
    return g


def assert_delivery_equivalent(before: TransferGraph, after: TransferGraph) -> None:
    assert before.delivery_map() == after.delivery_map()


def test_tip_reuse_reduces_tips_and_preserves_delivery() -> None:
    g = distribute_graph(8)
    assert g.tip_count() == 8
    out = tip_reuse(g)
    assert out.tip_count() == 1  # one shared tip for the clean distribute
    assert_delivery_equivalent(g, out)


def test_reagent_batch_reduces_tips_and_preserves_delivery() -> None:
    g = distribute_graph(6)
    out = reagent_batch(g)
    assert out.tip_count() == 1
    assert_delivery_equivalent(g, out)


def test_multichannel_pack_reduces_tips_and_preserves_delivery() -> None:
    g = column_graph()
    assert g.tip_count() == 8
    out = multichannel_pack(g)
    assert out.tip_count() == 1  # collapsed 8 rows into one channel group
    assert_delivery_equivalent(g, out)


def test_source_reorder_clusters_and_preserves_delivery() -> None:
    # Interleaved sources; reorder should cluster them so tip_reuse can merge.
    g = distribute_graph(4)
    g.transfers = [
        g.transfers[0],
        Transfer("reagents:A2", "plate:A2", 50, "p300", "other"),
        g.transfers[1],
        Transfer("reagents:A2", "plate:B2", 50, "p300", "other"),
    ]
    g.tip_classes.append(TipClass("other"))
    before = g.delivery_map()
    out = source_reorder(g)
    assert out.delivery_map() == before
    # After reorder + tip_reuse, each source clusters to one tip => 2 tips total.
    merged = tip_reuse(out)
    assert merged.tip_count() == 2


def test_full_pipeline_preserves_delivery_and_marks_optimized() -> None:
    g = distribute_graph(8)
    out = optimize(g)
    assert out.optimized is True
    assert_delivery_equivalent(g, out)
    assert out.tip_count() < g.tip_count()


def test_passes_never_merge_across_tip_classes() -> None:
    # Two transfers, same source, DIFFERENT tip classes must not share a tip.
    g = distribute_graph(1)
    g.transfers.append(Transfer("reagents:A1", "plate:B1", 50, "p300", "different"))
    g.tip_classes.append(TipClass("different"))
    out = tip_reuse(g)
    # They differ in tip_class, so no shared group -> still 2 tips.
    assert out.tip_count() == 2
    groups = {t.tip_group for t in out.transfers if t.tip_group is not None}
    # No group spans both classes.
    for gid in groups:
        classes = {t.tip_class for t in out.transfers if t.tip_group == gid}
        assert len(classes) == 1
