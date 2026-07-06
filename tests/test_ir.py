"""Unit tests for the TransferGraph IR."""

from __future__ import annotations

from pipettec.ir import Instrument, Labware, Transfer, TransferGraph


def _g() -> TransferGraph:
    g = TransferGraph()
    g.labware = [
        Labware("plate", "corning_96_wellplate_360ul_flat", "1"),
        Labware("tips", "opentrons_96_tiprack_300ul", "3"),
    ]
    g.instruments = [Instrument("p300", "p300_single_gen2", "right", ("tips",))]
    g.transfers = [
        Transfer("reagents:A1", "plate:A1", 50, "p300", "x"),
        Transfer("reagents:A1", "plate:B1", 50, "p300", "x"),
    ]
    return g


def test_well_accessors() -> None:
    t = Transfer("src:A1", "dst:H12", 10, "p300", "c")
    assert t.source_labware == "src"
    assert t.source_well == "A1"
    assert t.dest_labware == "dst"
    assert t.dest_well == "H12"


def test_delivery_map_sums_per_pair() -> None:
    g = _g()
    g.transfers.append(Transfer("reagents:A1", "plate:A1", 10, "p300", "x"))
    dm = g.delivery_map()
    assert dm[("reagents:A1", "plate:A1")] == 60
    assert dm[("reagents:A1", "plate:B1")] == 50


def test_tip_count_naive_is_one_per_transfer() -> None:
    g = _g()
    assert g.tip_count() == 2


def test_tip_count_shared_group() -> None:
    g = _g()
    from dataclasses import replace

    g.transfers = [replace(t, tip_group=7) for t in g.transfers]
    assert g.tip_count() == 1


def test_lookup_errors() -> None:
    g = _g()
    assert g.labware_by_id("plate").slot == "1"
    try:
        g.instrument_by_id("nope")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass


def test_copy_is_independent() -> None:
    g = _g()
    c = g.copy()
    c.transfers.append(Transfer("reagents:A1", "plate:C1", 5, "p300", "x"))
    assert len(g.transfers) == 2
    assert len(c.transfers) == 3
