"""Corpus / environment-sanity test.

Confirms the pinned ``opentrons==8.8.2`` simulator accepts a minimal hand-written OT-2 protocol
(API v2). This is not our codegen — it is a canary that the environment can simulate OT-2
protocols at all, catching accidental version drift (9.x drops OT-2 simulate support).
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import simulate

# A minimal, hand-written OT-2 protocol representative of published protocols.
_MINIMAL_OT2 = '''from opentrons import protocol_api

metadata = {"protocolName": "corpus canary", "apiLevel": "2.15"}


def run(protocol: protocol_api.ProtocolContext) -> None:
    plate = protocol.load_labware("corning_96_wellplate_360ul_flat", "1")
    tips = protocol.load_labware("opentrons_96_tiprack_300ul", "3")
    pip = protocol.load_instrument("p300_single_gen2", "right", tip_racks=[tips])
    pip.pick_up_tip()
    pip.aspirate(100, plate["A1"])
    pip.dispense(100, plate["B1"])
    pip.drop_tip()
'''


def test_opentrons_version_pinned() -> None:
    import opentrons

    major = int(opentrons.__version__.split(".")[0])
    assert major == 8, f"opentrons must be pinned <9 (OT-2 simulate); got {opentrons.__version__}"


def test_minimal_published_style_protocol_simulates(tmp_path: Path) -> None:
    p = tmp_path / "corpus.py"
    p.write_text(_MINIMAL_OT2)
    result = simulate(p)
    assert result.returncode == 0, result.stderr[-2000:]
