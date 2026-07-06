"""Property-based tests (Hypothesis).

Three properties, per PROJECT.md:

1. delivery-equivalence: optimize() preserves the per-(source,dest) delivery map (>=500 specs).
2. valid-spec: a generated valid spec compiles + validates cleanly (a subset is also simulated
   in the integration test to keep this fast; here we assert compile+validate over many specs).
3. contamination-safety: no optimized tip group ever spans two tip classes.

These run fully in-process (no simulator subprocess), so we can afford >=500 examples cheaply.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pipettec.codegen import generate
from pipettec.passes import optimize
from pipettec.spec.models import (
    CherryPick,
    PcrSetup,
    PlateNormalization,
    SerialDilution,
)
from pipettec.spec.templates import (
    lower_cherry_pick,
    lower_pcr_setup,
    lower_plate_normalization,
    lower_serial_dilution,
)
from pipettec.validate import validate

_WELLS_96 = [f"{r}{c}" for c in range(1, 13) for r in "ABCDEFGH"]

MANY = 550


@st.composite
def serial_dilution_specs(draw: st.DrawFn) -> SerialDilution:
    n_comp = draw(st.integers(min_value=1, max_value=2))
    points = draw(st.integers(min_value=2, max_value=12))
    replicates = draw(st.integers(min_value=1, max_value=4))
    return SerialDilution(
        template="serial_dilution",
        compounds=[f"C{i}" for i in range(n_comp)],
        points=points,
        replicates=replicates,
        top_conc_uM=draw(st.floats(min_value=1, max_value=1000)),
        factor=draw(st.floats(min_value=1.5, max_value=10)),
        transfer_volume_ul=draw(st.sampled_from([20.0, 30.0, 50.0, 100.0])),
    )


@st.composite
def cherry_pick_specs(draw: st.DrawFn) -> CherryPick:
    n = draw(st.integers(min_value=1, max_value=20))
    sources = draw(st.lists(st.sampled_from(_WELLS_96), min_size=n, max_size=n))
    dests = draw(st.lists(st.sampled_from(_WELLS_96), min_size=n, max_size=n, unique=True))
    vol = draw(st.sampled_from([20.0, 25.0, 50.0, 100.0, 150.0]))
    transfers = [{"source": s, "dest": d, "volume": vol} for s, d in zip(sources, dests, strict=True)]
    return CherryPick(template="cherry_pick", transfers=transfers)


def _graph_for(spec):  # type: ignore[no-untyped-def]
    if isinstance(spec, SerialDilution):
        return lower_serial_dilution(spec)
    if isinstance(spec, CherryPick):
        return lower_cherry_pick(spec)
    if isinstance(spec, PlateNormalization):
        return lower_plate_normalization(spec)
    if isinstance(spec, PcrSetup):
        return lower_pcr_setup(spec)
    raise TypeError(type(spec))


@settings(max_examples=MANY, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.one_of(serial_dilution_specs(), cherry_pick_specs()))
def test_delivery_equivalence(spec) -> None:  # type: ignore[no-untyped-def]
    naive = _graph_for(spec)
    opt = optimize(_graph_for(spec))
    assert naive.delivery_map() == opt.delivery_map()


@settings(max_examples=MANY, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.one_of(serial_dilution_specs(), cherry_pick_specs()))
def test_contamination_safety(spec) -> None:  # type: ignore[no-untyped-def]
    opt = optimize(_graph_for(spec))
    group_classes: dict[int, set[str]] = {}
    for t in opt.transfers:
        if t.tip_group is not None:
            group_classes.setdefault(t.tip_group, set()).add(t.tip_class)
    for classes in group_classes.values():
        assert len(classes) == 1


@settings(max_examples=MANY, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(serial_dilution_specs())
def test_valid_spec_compiles_and_validates(spec: SerialDilution) -> None:
    opt = optimize(_graph_for(spec))
    validate(opt)  # must not raise
    code = generate(opt)
    assert "def run(" in code
    assert "requirements" in code
