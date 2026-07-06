"""Ground-truth geometry for the labware and pipettes PipetteC uses.

These numbers are taken directly from Opentrons' own labware/pipette definitions (verified
against ``opentrons==8.8.2`` via ``get_protocol_api('2.15')``). They let the validator reason
about well/tip capacities and let front-ends enumerate wells in the canonical Opentrons order
without loading a live protocol context.

Well order is column-major (``A1, B1, ... H1, A2, ...``) exactly as Opentrons' ``.wells()``
returns it, so codegen and validation agree with the simulator.
"""

from __future__ import annotations

from dataclasses import dataclass

ROWS_8 = "ABCDEFGH"
ROWS_16 = "ABCDEFGHIJKLMNOP"


@dataclass(frozen=True)
class LabwareDef:
    """Geometry of one labware definition."""

    load_name: str
    n_rows: int
    n_cols: int
    well_max_ul: float
    is_tiprack: bool = False

    @property
    def rows(self) -> str:
        return ROWS_16[: self.n_rows]

    def wells(self) -> list[str]:
        """Column-major well names, matching Opentrons ``.wells()`` order."""
        return [f"{r}{c}" for c in range(1, self.n_cols + 1) for r in self.rows]

    def columns(self) -> list[list[str]]:
        """List of columns, each a top-to-bottom list of well names."""
        return [[f"{r}{c}" for r in self.rows] for c in range(1, self.n_cols + 1)]


# Verified against opentrons 8.8.2.
LABWARE: dict[str, LabwareDef] = {
    "corning_96_wellplate_360ul_flat": LabwareDef(
        "corning_96_wellplate_360ul_flat", 8, 12, 360.0
    ),
    "biorad_96_wellplate_200ul_pcr": LabwareDef(
        "biorad_96_wellplate_200ul_pcr", 8, 12, 200.0
    ),
    "corning_384_wellplate_112ul_flat": LabwareDef(
        "corning_384_wellplate_112ul_flat", 16, 24, 112.0
    ),
    "nest_12_reservoir_15ml": LabwareDef("nest_12_reservoir_15ml", 1, 12, 15000.0),
    "nest_1_reservoir_195ml": LabwareDef("nest_1_reservoir_195ml", 1, 1, 195000.0),
    "opentrons_96_tiprack_300ul": LabwareDef(
        "opentrons_96_tiprack_300ul", 8, 12, 300.0, is_tiprack=True
    ),
    "opentrons_96_tiprack_20ul": LabwareDef(
        "opentrons_96_tiprack_20ul", 8, 12, 20.0, is_tiprack=True
    ),
}


@dataclass(frozen=True)
class PipetteDef:
    """Working volume range and channel count of a pipette, plus its default tip rack."""

    model: str
    channels: int
    min_ul: float
    max_ul: float
    default_tiprack: str


PIPETTES: dict[str, PipetteDef] = {
    "p300_single_gen2": PipetteDef("p300_single_gen2", 1, 20.0, 300.0, "opentrons_96_tiprack_300ul"),
    "p20_single_gen2": PipetteDef("p20_single_gen2", 1, 1.0, 20.0, "opentrons_96_tiprack_20ul"),
    "p300_multi_gen2": PipetteDef("p300_multi_gen2", 8, 20.0, 300.0, "opentrons_96_tiprack_300ul"),
    "p20_multi_gen2": PipetteDef("p20_multi_gen2", 8, 1.0, 20.0, "opentrons_96_tiprack_20ul"),
}


def tiprack_capacity(load_name: str) -> int:
    """Number of tips on a rack (all supported racks are 96)."""
    d = LABWARE.get(load_name)
    if d is None or not d.is_tiprack:
        raise KeyError(f"not a known tip rack: {load_name!r}")
    return d.n_rows * d.n_cols
