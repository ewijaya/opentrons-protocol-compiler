"""Snapshot tests: codegen output is stable per template.

Snapshots live in ``tests/snapshots/<name>.py``. Regenerate intentionally with:
    PIPETTEC_UPDATE_SNAPSHOTS=1 pytest tests/test_codegen_snapshot.py
An unintended codegen change fails the test (a meaningful diff in CI).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipettec.codegen import generate
from pipettec.compiler import front_end_for
from pipettec.passes import optimize

SNAP_DIR = Path(__file__).parent / "snapshots"
ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

CASES = [
    "dose_response.yaml",
    "plate_normalization.yaml",
    "cherry_pick.yaml",
    "reformat_96_to_384.yaml",
    "pcr_setup.yaml",
    "picklist.csv",
]


@pytest.mark.parametrize("spec_file", CASES)
def test_codegen_snapshot(spec_file: str) -> None:
    graph = optimize(front_end_for(EXAMPLES / spec_file))
    code = generate(graph)
    snap = SNAP_DIR / (Path(spec_file).stem + ".py")
    if os.environ.get("PIPETTEC_UPDATE_SNAPSHOTS"):
        SNAP_DIR.mkdir(exist_ok=True)
        snap.write_text(code)
        pytest.skip(f"updated snapshot {snap.name}")
    assert snap.exists(), f"missing snapshot {snap}; run with PIPETTEC_UPDATE_SNAPSHOTS=1"
    assert code == snap.read_text(), f"codegen output drifted from snapshot {snap.name}"


def test_codegen_deterministic() -> None:
    graph = optimize(front_end_for(EXAMPLES / "dose_response.yaml"))
    assert generate(graph) == generate(optimize(front_end_for(EXAMPLES / "dose_response.yaml")))
