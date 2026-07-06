"""Shared test fixtures and helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
VENV_SIMULATE = ROOT / ".venv" / "bin" / "opentrons_simulate"


def simulate(protocol_path: str | Path) -> subprocess.CompletedProcess[str]:
    """Run the real ``opentrons_simulate`` on a protocol file; return the completed process.

    This is the correctness gate: exit 0 means the protocol is valid. Never mocked.
    """
    return subprocess.run(
        [str(VENV_SIMULATE), str(protocol_path)],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES
