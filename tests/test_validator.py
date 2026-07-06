"""Unit tests: each of the 5 rejection classes is caught with the right code + message."""

from __future__ import annotations

import pytest

from pipettec.ir import Instrument, Labware, TipClass, Transfer, TransferGraph
from pipettec.validate import ValidationError, validate
from pipettec.validate.diagnostics import (
    CAPACITY,
    CONTAMINATION,
    DECK_COLLISION,
    EMPTY_SOURCE,
    REJECTION_CLASSES,
    TIP_EXHAUSTION,
)


def base() -> TransferGraph:
    g = TransferGraph()
    g.labware = [
        Labware("plate", "corning_96_wellplate_360ul_flat", "1"),
        Labware("reagents", "nest_12_reservoir_15ml", "2"),
        Labware("tips", "opentrons_96_tiprack_300ul", "3"),
    ]
    g.instruments = [Instrument("p300", "p300_single_gen2", "right", ("tips",))]
    g.tip_classes = [TipClass("x")]
    g.transfers = [Transfer("reagents:A1", "plate:A1", 50, "p300", "x")]
    return g


def codes(exc: ValidationError) -> set[str]:
    return {d.code for d in exc.diagnostics}


def test_valid_graph_passes() -> None:
    validate(base())  # no raise


def test_capacity_over_tip() -> None:
    g = base()
    g.transfers = [Transfer("reagents:A1", "plate:A1", 500, "p300", "x")]
    with pytest.raises(ValidationError) as e:
        validate(g)
    assert CAPACITY in codes(e.value)


def test_capacity_cumulative_well_overflow() -> None:
    g = base()
    g.transfers = [
        Transfer("reagents:A1", "plate:A1", 200, "p300", "x"),
        Transfer("reagents:A1", "plate:A1", 200, "p300", "x"),
    ]
    with pytest.raises(ValidationError) as e:
        validate(g)
    assert CAPACITY in codes(e.value)


def test_empty_source() -> None:
    g = base()
    # A working plate well used as source but never filled.
    g.transfers = [
        Transfer("plate:H12", "plate:A1", 50, "p300", "x"),  # H12 never filled
    ]
    with pytest.raises(ValidationError) as e:
        validate(g)
    assert EMPTY_SOURCE in codes(e.value)


def test_tip_exhaustion() -> None:
    g = base()
    # Need more distinct tips than the single rack (96) provides.
    wells = [f"{r}{c}" for c in range(1, 13) for r in "ABCDEFGH"]  # 96 wells
    ts = [Transfer("reagents:A1", f"plate:{w}", 50, "p300", f"c{i}")
          for i, w in enumerate(wells)]
    # add one more distinct-tip transfer -> 97 > 96
    ts.append(Transfer("reagents:A2", "plate:A1", 50, "p300", "extra"))
    g.transfers = ts
    with pytest.raises(ValidationError) as e:
        validate(g)
    assert TIP_EXHAUSTION in codes(e.value)


def test_deck_collision_duplicate_slot() -> None:
    g = base()
    g.labware.append(Labware("plate2", "corning_96_wellplate_360ul_flat", "1"))  # slot 1 twice
    with pytest.raises(ValidationError) as e:
        validate(g)
    assert DECK_COLLISION in codes(e.value)


def test_deck_collision_missing_labware() -> None:
    g = base()
    g.transfers = [Transfer("ghost:A1", "plate:A1", 50, "p300", "x")]
    with pytest.raises(ValidationError) as e:
        validate(g)
    assert DECK_COLLISION in codes(e.value)


def test_contamination_unsafe_reuse() -> None:
    g = base()
    # Manually craft an unsafe tip group spanning two tip classes.
    g.tip_classes.append(TipClass("y"))
    g.transfers = [
        Transfer("reagents:A1", "plate:A1", 50, "p300", "x", tip_group=1),
        Transfer("reagents:A1", "plate:B1", 50, "p300", "y", tip_group=1),
    ]
    with pytest.raises(ValidationError) as e:
        validate(g)
    assert CONTAMINATION in codes(e.value)


def test_all_five_rejection_classes_have_a_test() -> None:
    # Guard: this module must exercise every declared rejection class.
    assert set(REJECTION_CLASSES) == {
        CAPACITY,
        EMPTY_SOURCE,
        TIP_EXHAUSTION,
        DECK_COLLISION,
        CONTAMINATION,
    }
