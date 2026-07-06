"""Naive-vs-optimized benchmark, computed from one IR per spec.

Emits a Markdown table (tips, steps, est. time) for each example and the dose-response headline.
Because naive and optimized come from the *same* front-end IR (optimizer off vs on), the
comparison is apples-to-apples and cannot be cherry-picked (see PROJECT.md § benchmarking).

Usage:
    python benchmarks/bench.py            # print the table
    python benchmarks/bench.py --check    # also assert tip reduction >= 60% on dose-response
    python benchmarks/bench.py --readme   # rewrite the metrics block in README.md
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pipettec.compiler import front_end_for  # noqa: E402
from pipettec.passes import optimize  # noqa: E402
from pipettec.report.metrics import (  # noqa: E402
    compute_metrics,
    tip_reduction_pct,
)

# The dose-response benchmark headline must clear this bar (PRD: >=60%, target ~75%).
DOSE_RESPONSE_MIN_REDUCTION = 60.0

BENCH_SPECS = [
    ("dose_response", ROOT / "examples" / "dose_response.yaml"),
    ("plate_normalization", ROOT / "examples" / "plate_normalization.yaml"),
    ("cherry_pick", ROOT / "examples" / "cherry_pick.yaml"),
    ("reformat_96_to_384", ROOT / "examples" / "reformat_96_to_384.yaml"),
    ("pcr_setup", ROOT / "examples" / "pcr_setup.yaml"),
    ("picklist (Echo)", ROOT / "examples" / "picklist.csv"),
]

MARKER_START = "<!-- BENCH:START -->"
MARKER_END = "<!-- BENCH:END -->"


def _row(name: str, spec_path: Path) -> tuple[str, float]:
    naive = front_end_for(spec_path)
    opt = optimize(front_end_for(spec_path))
    n = compute_metrics(naive)
    o = compute_metrics(opt)
    red = tip_reduction_pct(naive, opt)

    def pct(a: int, b: int) -> str:
        return "0%" if a == 0 else f"-{round((a - b) / a * 100)}%"

    line = (
        f"| {name} | {n.tips} | {o.tips} | **{pct(n.tips, o.tips)}** "
        f"| {n.steps} | {o.steps} | {n.est_minutes} | {o.est_minutes} |"
    )
    return line, red


def build_table() -> tuple[str, float]:
    header = [
        "| Spec | Tips (naive) | Tips (opt) | Tip reduction | Steps (naive) | Steps (opt) | Time naive (min) | Time opt (min) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    rows = []
    dose_reduction = 0.0
    for name, path in BENCH_SPECS:
        line, red = _row(name, path)
        rows.append(line)
        if name == "dose_response":
            dose_reduction = red
    return "\n".join(header + rows), dose_reduction


def main(argv: list[str]) -> int:
    table, dose_reduction = build_table()
    print(table)
    print()
    print(f"dose_response tip reduction: {dose_reduction}%")

    if "--readme" in argv:
        readme = ROOT / "README.md"
        text = readme.read_text()
        if MARKER_START in text and MARKER_END in text:
            pre = text.split(MARKER_START)[0]
            post = text.split(MARKER_END)[1]
            text = f"{pre}{MARKER_START}\n{table}\n{MARKER_END}{post}"
            readme.write_text(text)
            print(f"updated {readme}")

    if "--check" in argv:
        if dose_reduction < DOSE_RESPONSE_MIN_REDUCTION:
            print(
                f"BENCH FAIL: dose-response tip reduction {dose_reduction}% "
                f"< {DOSE_RESPONSE_MIN_REDUCTION}%",
                file=sys.stderr,
            )
            return 1
        print(f"BENCH OK: dose-response tip reduction {dose_reduction}% >= {DOSE_RESPONSE_MIN_REDUCTION}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
