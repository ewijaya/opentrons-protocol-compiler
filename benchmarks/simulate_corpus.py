"""Scaled validation: drive the REAL ``opentrons_simulate`` on >=500 generated valid specs.

This is the heavyweight cousin of ``tests/test_property_simulate.py``. Each simulation spawns an
``opentrons_simulate`` subprocess (~2s of import + dry-run), so 500 of them take minutes — too
slow for the per-commit gate, which instead samples a dozen. Run this on demand to back the
"≥500 valid specs simulate cleanly" success criterion at full scale:

    python benchmarks/simulate_corpus.py            # 500 specs, prints PASS/FAIL counts
    python benchmarks/simulate_corpus.py --n 200    # smaller batch

Every spec is a valid serial-dilution / cherry-pick / plate-normalization / pcr-setup instance;
the simulator is never mocked. Exit 0 only if every generated protocol simulates cleanly.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipettec.codegen import generate  # noqa: E402
from pipettec.passes import optimize  # noqa: E402
from pipettec.spec.models import (  # noqa: E402
    CherryPick,
    PcrSetup,
    PlateNormalization,
    SerialDilution,
)
from pipettec.spec.templates import (  # noqa: E402
    lower_cherry_pick,
    lower_pcr_setup,
    lower_plate_normalization,
    lower_serial_dilution,
)
from pipettec.validate import validate  # noqa: E402

SIMULATE = ROOT / ".venv" / "bin" / "opentrons_simulate"
_WELLS = [f"{r}{c}" for c in range(1, 13) for r in "ABCDEFGH"]


def _specs(n: int) -> list:
    """Deterministically enumerate a diverse corpus of valid specs (no RNG)."""
    out: list = []
    # serial dilutions across every valid (compounds, replicates, points, volume)
    for c in (1, 2):
        for r in (1, 2, 3, 4, 8):
            if c * r > 8:
                continue
            for p in range(2, 13):
                for v in (20.0, 30.0, 50.0, 100.0):
                    out.append(
                        SerialDilution(
                            template="serial_dilution",
                            compounds=[f"C{k}" for k in range(c)],
                            points=p,
                            replicates=r,
                            top_conc_uM=100,
                            factor=2 + (p % 5),
                            transfer_volume_ul=v,
                        )
                    )
    # cherry picks of varying size
    for size in range(1, 40):
        transfers = [
            {"source": _WELLS[i % 96], "dest": _WELLS[(i * 7 + 1) % 96], "volume": 20.0 + (i % 5) * 20}
            for i in range(size)
        ]
        # dedup dests to avoid overflow
        seen: dict[str, dict] = {}
        for t in transfers:
            seen[t["dest"]] = t
        out.append(CherryPick(template="cherry_pick", transfers=list(seen.values())))
    # plate normalizations
    for k in range(1, 20):
        wells = _WELLS[:k]
        out.append(
            PlateNormalization(
                template="plate_normalization",
                wells=wells,
                current_volume_ul=[50.0 + (i % 3) * 20 for i in range(k)],
                target_volume_ul=200.0,
            )
        )
    # pcr setups
    for rx in range(1, 40):
        out.append(PcrSetup(template="pcr_setup", reactions=rx))
    # cycle to reach n
    full: list = []
    i = 0
    while len(full) < n:
        full.append(out[i % len(out)])
        i += 1
    return full


def _lower(spec):  # type: ignore[no-untyped-def]
    if isinstance(spec, SerialDilution):
        return lower_serial_dilution(spec)
    if isinstance(spec, CherryPick):
        return lower_cherry_pick(spec)
    if isinstance(spec, PlateNormalization):
        return lower_plate_normalization(spec)
    if isinstance(spec, PcrSetup):
        return lower_pcr_setup(spec)
    raise TypeError(type(spec))


def _build_and_sim(spec) -> tuple[bool, str]:  # type: ignore[no-untyped-def]
    graph = optimize(_lower(spec))
    validate(graph)
    code = generate(graph)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run([str(SIMULATE), path], capture_output=True, text=True)
    finally:
        Path(path).unlink(missing_ok=True)
    if r.returncode != 0:
        return False, (r.stdout + r.stderr).strip().splitlines()[-1][:120]
    return True, ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)

    specs = _specs(args.n)
    ok = 0
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for passed, msg in ex.map(_build_and_sim, specs):
            if passed:
                ok += 1
            else:
                failures.append(msg)
    print(f"simulated {len(specs)} valid specs: PASS={ok} FAIL={len(failures)}")
    for m in failures[:10]:
        print(f"  FAIL: {m}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
