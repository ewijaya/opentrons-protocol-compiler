"""Integration tests: full CLI compile -> real opentrons_simulate exit 0.

The simulator is the source of truth and is never mocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipettec.cli import main
from tests.conftest import EXAMPLES, simulate

EXAMPLE_SPECS = [
    "dose_response.yaml",
    "plate_normalization.yaml",
    "cherry_pick.yaml",
    "reformat_96_to_384.yaml",
    "pcr_setup.yaml",
    "picklist.csv",
]


@pytest.mark.parametrize("spec_file", EXAMPLE_SPECS)
def test_compile_then_simulate(spec_file: str, tmp_path: Path) -> None:
    out = tmp_path / (Path(spec_file).stem + ".py")
    rc = main(["compile", str(EXAMPLES / spec_file), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    result = simulate(out)
    assert result.returncode == 0, f"simulate failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"


def test_naive_single_channel_spec_simulates(tmp_path: Path) -> None:
    # For a single-channel template the naive (unoptimized) protocol is itself runnable.
    spec = EXAMPLES / "plate_normalization.yaml"
    naive = tmp_path / "naive.py"
    opt = tmp_path / "opt.py"
    assert main(["compile", str(spec), "-o", str(naive), "--no-optimize"]) == 0
    assert main(["compile", str(spec), "-o", str(opt)]) == 0
    assert simulate(naive).returncode == 0
    assert simulate(opt).returncode == 0


def test_optimized_uses_fewer_tips_than_naive() -> None:
    from pipettec.compiler import front_end_for
    from pipettec.passes import optimize

    naive = front_end_for(EXAMPLES / "dose_response.yaml")
    opt = optimize(front_end_for(EXAMPLES / "dose_response.yaml"))
    assert opt.tip_count() < naive.tip_count()


def test_cli_validate_rejects_bad_spec(capsys) -> None:  # type: ignore[no-untyped-def]
    rc = main(["validate", str(EXAMPLES / "bad" / "capacity_over_tip.yaml")])
    assert rc == 1


def test_cli_validate_accepts_good_spec() -> None:
    rc = main(["validate", str(EXAMPLES / "dose_response.yaml")])
    assert rc == 0


def test_cli_report_runs(capsys) -> None:  # type: ignore[no-untyped-def]
    rc = main(["report", str(EXAMPLES / "dose_response.yaml")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Tips" in out


def test_cli_render_writes_files(tmp_path: Path) -> None:
    deck = tmp_path / "deck.svg"
    heat = tmp_path / "heat.png"
    rc = main(["render", str(EXAMPLES / "dose_response.yaml"), "--deck", str(deck), "--heatmap", str(heat)])
    assert rc == 0
    assert deck.exists() and deck.stat().st_size > 0
    assert heat.exists() and heat.stat().st_size > 0
