"""Valid-spec-simulates property, exercised with the REAL simulator on fuzzer output.

The full delivery-equivalence / valid-spec properties run 550 in-process specs each
(``test_property.py``). Running the ~2s subprocess simulator 550 times would make CI take ~17
minutes, so here we drive ``opentrons_simulate`` on a bounded sample of *fuzzer-generated* valid
specs (not just the hand-written examples). This proves that generated-spec output — not only the
curated examples — simulates cleanly, without a pathological CI runtime. The simulator is never
mocked.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings

from pipettec.codegen import generate
from pipettec.passes import optimize
from pipettec.validate import validate
from tests.conftest import simulate
from tests.test_property import _graph_for, serial_dilution_specs

# Bounded: enough distinct fuzzer specs to be convincing, small enough for CI (~2s each).
SIM_SAMPLE = 12


@settings(
    max_examples=SIM_SAMPLE,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(serial_dilution_specs())
def test_generated_valid_spec_simulates(spec) -> None:  # type: ignore[no-untyped-def]
    graph = optimize(_graph_for(spec))
    validate(graph)
    code = generate(graph)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "protocol.py"
        out.write_text(code)
        result = simulate(out)
    assert result.returncode == 0, (
        f"fuzzer-generated valid spec failed to simulate:\n{result.stdout[-1500:]}\n{result.stderr[-1500:]}"
    )
