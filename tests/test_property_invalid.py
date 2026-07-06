"""Invalid-spec property: fuzzed invalid IR is ALWAYS rejected cleanly (never crashes).

We build graphs that deliberately violate a rejection class and assert ``validate`` raises a
structured :class:`ValidationError` (not an arbitrary exception, not a pass). >=500 examples.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pipettec.ir import Instrument, Labware, TipClass, Transfer, TransferGraph
from pipettec.validate import ValidationError, validate

_WELLS = [f"{r}{c}" for c in range(1, 13) for r in "ABCDEFGH"]
MANY = 550


def _deck() -> TransferGraph:
    g = TransferGraph()
    g.labware = [
        Labware("plate", "corning_96_wellplate_360ul_flat", "1"),
        Labware("reagents", "nest_12_reservoir_15ml", "2"),
        Labware("tips", "opentrons_96_tiprack_300ul", "3"),
    ]
    g.instruments = [Instrument("p300", "p300_single_gen2", "right", ("tips",))]
    g.tip_classes = [TipClass("x")]
    return g


@st.composite
def invalid_graphs(draw: st.DrawFn) -> TransferGraph:
    """Produce a graph that violates at least one rejection class."""
    g = _deck()
    kind = draw(st.sampled_from(["capacity", "empty", "collision", "contam", "missing"]))
    w = draw(st.sampled_from(_WELLS))
    if kind == "capacity":
        vol = draw(st.floats(min_value=301, max_value=5000))
        g.transfers = [Transfer("reagents:A1", f"plate:{w}", vol, "p300", "x")]
    elif kind == "empty":
        # working-plate well used as source but never filled (source must differ from every
        # dest so it is genuinely never produced on-deck).
        dest = draw(st.sampled_from(_WELLS))
        src_pool = [x for x in _WELLS if x != dest]
        src = draw(st.sampled_from(src_pool))
        g.transfers = [Transfer(f"plate:{src}", f"plate:{dest}", 50, "p300", "x")]
    elif kind == "collision":
        g.labware.append(Labware("dup", "corning_96_wellplate_360ul_flat", "1"))
        g.transfers = [Transfer("reagents:A1", f"plate:{w}", 50, "p300", "x")]
    elif kind == "contam":
        g.tip_classes.append(TipClass("y"))
        g.transfers = [
            Transfer("reagents:A1", "plate:A1", 50, "p300", "x", tip_group=1),
            Transfer("reagents:A1", f"plate:{w}", 50, "p300", "y", tip_group=1),
        ]
    else:  # missing labware
        g.transfers = [Transfer("ghost:A1", f"plate:{w}", 50, "p300", "x")]
    return g


@settings(max_examples=MANY, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(invalid_graphs())
def test_invalid_specs_always_rejected_cleanly(g: TransferGraph) -> None:
    try:
        validate(g)
    except ValidationError as e:
        assert e.diagnostics  # structured, non-empty
        assert all(d.code for d in e.diagnostics)
        return
    raise AssertionError("expected the invalid graph to be rejected")
