"""Lower each YAML template model onto the shared ``TransferGraph`` IR.

Each function builds a standard OT-2 deck (plate + reservoir + tip rack + pipette) and emits an
ordered list of :class:`Transfer` objects. Volumes and wells are chosen so the generated
protocol simulates cleanly under ``opentrons==8.8.2`` (p300 range 20–300 uL, 96/384 geometry).

The IR produced here is *naive* (no tip groups / channel groups); the optimizer adds those.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pipettec.ir import Instrument, Labware, TipClass, Transfer, TransferGraph
from pipettec.labware_defs import LABWARE, ROWS_8
from pipettec.spec.models import (
    CherryPick,
    PcrSetup,
    PlateNormalization,
    Reformat96to384,
    SerialDilution,
)

# A standard single-channel deck used by most templates.
_PLATE = Labware("plate", "corning_96_wellplate_360ul_flat", "1")
_RESERVOIR = Labware("reagents", "nest_12_reservoir_15ml", "2")
_TIPRACK = Labware("tips", "opentrons_96_tiprack_300ul", "3")
_TIPRACK2 = Labware("tips2", "opentrons_96_tiprack_300ul", "6")
_P300 = Instrument(
    "p300", "p300_single_gen2", "right", ("tips", "tips2"), channels=1, min_volume_ul=20.0, max_volume_ul=300.0
)

# A multi-channel deck for reformat.
_P300_MULTI = Instrument(
    "p300m", "p300_multi_gen2", "left", ("tips", "tips2"), channels=8, min_volume_ul=20.0, max_volume_ul=300.0
)


def _base_graph(name: str, description: str) -> TransferGraph:
    g = TransferGraph()
    g.metadata = {"name": name, "apiLevel": "2.15", "description": description, "author": "PipetteC"}
    return g


def _plate_block_wells(points: int, replicate_col: int) -> list[str]:
    """Wells for one dilution series: rows A..(points) down a single column."""
    return [f"{ROWS_8[i]}{replicate_col}" for i in range(points)]


def lower_serial_dilution(spec: SerialDilution) -> TransferGraph:
    """Serial dilution laid out the way it is actually run on an OT-2 with a multi pipette.

    Layout (the standard dose-response layout):

    * **Points run across columns** ``1..points``; **replicates run down rows** ``A..H``.
    * Each (compound) occupies a horizontal band of ``replicates`` rows.
    * Diluent is distributed into every well of points ``2..N`` (one clean tip).
    * The top concentration is loaded into column 1 of the band from the compound stock.
    * Serial dilution then moves ``vol`` from column ``k`` to column ``k+1`` for the whole band.

    Because each dilution step is a straight column-to-column move across all rows of the band,
    an 8-channel pipette does a full 8-row band in a single move — the ``multichannel_pack`` pass
    collapses the per-row transfers 8:1. This is the real tip win for dose-response plates.
    """
    g = _base_graph(spec.name, f"Serial dilution: {spec.compounds} x{spec.points}pt f={spec.factor}")
    g.labware = [_PLATE, _RESERVOIR, _TIPRACK, _TIPRACK2]
    g.instruments = [_P300_MULTI, _P300]
    g.tip_classes = [TipClass("diluent", "clean diluent distribution")]
    for c in spec.compounds:
        g.tip_classes.append(TipClass(f"stock:{c}", f"clean {c} stock"))
        g.tip_classes.append(TipClass(f"dilute:{c}", f"contaminated serial mixing for {c}"))

    vol = spec.transfer_volume_ul
    transfers: list[Transfer] = []
    row0 = 0
    for c_i, compound in enumerate(spec.compounds):
        stock_well = f"reagents:A{2 + c_i}"  # A2, A3, ...
        band_rows = ROWS_8[row0 : row0 + spec.replicates]
        # 1) diluent into points 2..N across the whole band (clean, tip-reusable distribute).
        for col in range(2, spec.points + 1):
            for r in band_rows:
                transfers.append(
                    Transfer(
                        source="reagents:A1",
                        dest=f"plate:{r}{col}",
                        volume=vol,
                        instrument="p300m",
                        tip_class="diluent",
                    )
                )
        # 2) load top concentration into column 1 of the band from the compound stock.
        for r in band_rows:
            transfers.append(
                Transfer(
                    source=stock_well,
                    dest=f"plate:{r}1",
                    volume=vol,
                    instrument="p300m",
                    tip_class=f"stock:{compound}",
                )
            )
        # 3) serial dilution across columns: move vol from col k to col k+1 for the band.
        for col in range(1, spec.points):
            for r in band_rows:
                transfers.append(
                    Transfer(
                        source=f"plate:{r}{col}",
                        dest=f"plate:{r}{col + 1}",
                        volume=vol,
                        instrument="p300m",
                        tip_class=f"dilute:{compound}",
                    )
                )
        row0 += spec.replicates
    g.transfers = transfers
    return g


def lower_plate_normalization(spec: PlateNormalization) -> TransferGraph:
    """Add diluent to each well to reach ``target_volume_ul`` (clean distribute)."""
    g = _base_graph(spec.name, "Normalize wells to a common volume with diluent")
    g.labware = [_PLATE, _RESERVOIR, _TIPRACK, _TIPRACK2]
    g.instruments = [_P300]
    g.tip_classes = [TipClass("diluent", "clean diluent distribution")]
    transfers: list[Transfer] = []
    for well, cur in zip(spec.wells, spec.current_volume_ul, strict=True):
        add = round(spec.target_volume_ul - cur, 3)
        if add <= 0:
            continue
        transfers.append(
            Transfer(
                source="reagents:A1",
                dest=f"plate:{well}",
                volume=add,
                instrument="p300",
                tip_class="diluent",
            )
        )
    g.transfers = transfers
    return g


def lower_cherry_pick(spec: CherryPick) -> TransferGraph:
    """Arbitrary transfers. Each row: {source, dest, volume} with well refs 'plate:A1' or bare.

    Bare well names (e.g. 'A1') are placed on the source/dest plates. This lowering is shared by
    the Echo picklist front-end.
    """
    g = _base_graph(spec.name, "Cherry-pick / hit-pick arbitrary transfers")
    src_plate = Labware("src", "corning_96_wellplate_360ul_flat", "1")
    dst_plate = Labware("dst", "corning_96_wellplate_360ul_flat", "2")
    g.labware = [src_plate, dst_plate, _TIPRACK, _TIPRACK2]
    g.instruments = [_P300]
    g.tip_classes = [TipClass("cherry", "one tip per distinct source, no cross-contamination")]
    transfers: list[Transfer] = []
    for row in spec.transfers:
        source = _qualify(row["source"], "src")
        dest = _qualify(row["dest"], "dst")
        transfers.append(
            Transfer(
                source=source,
                dest=dest,
                volume=float(row["volume"]),
                instrument="p300",
                # Each distinct source is its own tip class (no cross-source sharing).
                tip_class=f"cherry:{source}",
            )
        )
    g.transfers = transfers
    return g


def _qualify(ref: str, default_labware: str) -> str:
    return ref if ":" in ref else f"{default_labware}:{ref}"


def lower_reformat_96_to_384(spec: Reformat96to384) -> TransferGraph:
    """Consolidate up to four 96-well plates into the four interleaved quadrants of a 384.

    Each 96 source well ``(row r, col c)`` maps into the 384 plate at the interleaved position
    for its quadrant: 384 row ``2*r + r_off``, 384 col ``2*c + c_off``. Because the 384's rows
    are interleaved, a straight 8-channel column move does not line up, so this lowering uses a
    single-channel pipette (one clean tip per source, no cross-contamination). Each source plate
    contributes 96 transfers; up to four plates fit within the two 300 uL tip racks.
    """
    g = _base_graph(spec.name, "Reformat 96-well plates into a 384-well plate")
    plate384 = Labware("plate384", "corning_384_wellplate_112ul_flat", "1")
    g.labware = [plate384, _TIPRACK, _TIPRACK2]
    # Source 96 plates on slots 4,5,7,8.
    slots = ["4", "5", "7", "8"]
    for i, _sp in enumerate(spec.source_plates):
        g.labware.insert(1 + i, Labware(f"src{i}", "corning_96_wellplate_360ul_flat", slots[i]))
    g.instruments = [_P300]
    g.tip_classes = [TipClass("reformat", "clean plate consolidation, one tip per source well")]

    # Quadrant row/col offsets for interleaving 96 -> 384.
    quad_offsets = [(0, 0), (1, 0), (0, 1), (1, 1)]  # (row_offset, col_offset)
    rows384 = "ABCDEFGHIJKLMNOP"
    transfers: list[Transfer] = []
    for qi, _sp in enumerate(spec.source_plates):
        r_off, c_off = quad_offsets[qi]
        for col in range(1, 13):  # 96 has 12 columns
            for r_i in range(8):  # rows A..H
                src_well = f"{ROWS_8[r_i]}{col}"
                tgt_row = rows384[r_i * 2 + r_off]
                tgt_col = (col - 1) * 2 + 1 + c_off
                dst_well = f"{tgt_row}{tgt_col}"
                transfers.append(
                    Transfer(
                        source=f"src{qi}:{src_well}",
                        dest=f"plate384:{dst_well}",
                        volume=spec.volume_ul,
                        instrument="p300",
                        # Distinct source wells -> distinct tip classes (no cross-contamination).
                        tip_class=f"reformat:{qi}:{src_well}",
                    )
                )
    g.transfers = transfers
    return g


def lower_pcr_setup(spec: PcrSetup) -> TransferGraph:
    """Distribute mastermix from a reservoir to N wells, then add template to each.

    PCR volumes are small (a few uL), so this deck uses a p20 single-channel pipette whose
    working range (1–20 uL) covers both the mastermix and template additions.
    """
    g = _base_graph(spec.name, "PCR setup: mastermix distribution + template addition")
    pcr = Labware("pcr", "biorad_96_wellplate_200ul_pcr", "1")
    templates = Labware("templates", "corning_96_wellplate_360ul_flat", "4")
    tiprack20 = Labware("tips20", "opentrons_96_tiprack_20ul", "3")
    tiprack20b = Labware("tips20b", "opentrons_96_tiprack_20ul", "6")
    p20 = Instrument(
        "p20", "p20_single_gen2", "left", ("tips20", "tips20b"),
        channels=1, min_volume_ul=1.0, max_volume_ul=20.0,
    )
    g.labware = [pcr, _RESERVOIR, templates, tiprack20, tiprack20b]
    g.instruments = [p20]
    g.tip_classes = [
        TipClass("mastermix", "clean mastermix distribution"),
        TipClass("template", "per-sample template, one tip each"),
    ]
    wells = LABWARE["biorad_96_wellplate_200ul_pcr"].wells()[: spec.reactions]
    transfers: list[Transfer] = []
    # 1) mastermix into every reaction well (clean distribute from reservoir A1)
    for w in wells:
        transfers.append(
            Transfer(
                source="reagents:A1",
                dest=f"pcr:{w}",
                volume=spec.mastermix_volume_ul,
                instrument="p20",
                tip_class="mastermix",
            )
        )
    # 2) template from the templates plate (well-for-well), fresh tip each (no cross-contam)
    for w in wells:
        transfers.append(
            Transfer(
                source=f"templates:{w}",
                dest=f"pcr:{w}",
                volume=spec.template_volume_ul,
                instrument="p20",
                tip_class=f"template:{w}",
            )
        )
    g.transfers = transfers
    return g


LOWERINGS: dict[str, Callable[[Any], TransferGraph]] = {
    "serial_dilution": lower_serial_dilution,
    "plate_normalization": lower_plate_normalization,
    "cherry_pick": lower_cherry_pick,
    "reformat_96_to_384": lower_reformat_96_to_384,
    "pcr_setup": lower_pcr_setup,
}
