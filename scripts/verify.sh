#!/usr/bin/env bash
# PipetteC verification harness — the single quality gate.
#
# Runs the full local gate and prints a per-stage PASS/FAIL table, then exactly one final line:
#   VERIFY: ALL PASS                       (exit 0) when every stage passes
#   VERIFY: FAILED (<stage>, <stage>...)   (exit 1) otherwise
#
# Stages with nothing to check yet print "SKIP (not yet built)" and do NOT count as failures.
# The simulator and test stages must never auto-skip once examples exist.
#
# Contract (fixed from day one): ruff -> mypy -> pytest --cov(85% gate) -> compile+simulate every
# example -> benchmark. Uses the project .venv (Python 3.12, opentrons 8.8.2).

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

VENV="./.venv/bin"
PY="$VENV/python"
if [[ ! -x "$PY" ]]; then
  echo "FATAL: .venv not found; run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  echo "VERIFY: FAILED (env)"
  exit 1
fi

FAILED=()
declare -A STATUS

run_stage() {
  local name="$1"; shift
  echo "==> [$name] $*"
  if "$@"; then
    STATUS[$name]="PASS"
  else
    STATUS[$name]="FAIL"
    FAILED+=("$name")
  fi
}

skip_stage() {
  local name="$1" reason="$2"
  STATUS[$name]="SKIP ($reason)"
  echo "==> [$name] SKIP ($reason)"
}

# --- ruff ------------------------------------------------------------------------------------
run_stage ruff "$VENV/ruff" check src tests

# --- mypy ------------------------------------------------------------------------------------
run_stage mypy "$VENV/mypy" src

# --- pytest with coverage gate (85% on src) --------------------------------------------------
if [[ -d tests ]] && compgen -G "tests/test_*.py" > /dev/null; then
  run_stage pytest "$VENV/python" -m pytest --cov=pipettec --cov-report=term-missing --cov-fail-under=85
else
  skip_stage pytest "no tests yet"
fi

# --- compile + simulate every example --------------------------------------------------------
SIM_TMP="$(mktemp -d)"
simulate_examples() {
  local ok=1
  shopt -s nullglob
  local specs=(examples/*.yaml examples/*.yml examples/*.csv)
  if [[ ${#specs[@]} -eq 0 ]]; then
    echo "  (no examples yet)"
    return 0
  fi
  for spec in "${specs[@]}"; do
    local base out
    base="$(basename "$spec")"
    out="$SIM_TMP/${base%.*}.py"
    echo "  compile $spec"
    if ! "$VENV/pipettec" compile "$spec" -o "$out" >/dev/null 2>"$SIM_TMP/err.txt"; then
      echo "    COMPILE FAILED:"; sed 's/^/      /' "$SIM_TMP/err.txt"; ok=0; continue
    fi
    echo "  simulate $out"
    if ! "$VENV/opentrons_simulate" "$out" >/dev/null 2>"$SIM_TMP/simerr.txt"; then
      echo "    SIMULATE FAILED:"; tail -5 "$SIM_TMP/simerr.txt" | sed 's/^/      /'; ok=0; continue
    fi
  done
  # Bad specs (examples/bad/*) must be REJECTED (non-zero exit) by validate.
  local bad=(examples/bad/*.yaml)
  if [[ -e "${bad[0]:-}" ]]; then
    for spec in "${bad[@]}"; do
      echo "  reject-check $spec"
      if "$VENV/pipettec" validate "$spec" >/dev/null 2>&1; then
        echo "    EXPECTED REJECTION but validate passed"; ok=0
      fi
    done
  fi
  [[ $ok -eq 1 ]]
}
run_stage simulate simulate_examples

# --- benchmark -------------------------------------------------------------------------------
if [[ -f benchmarks/bench.py ]]; then
  run_stage benchmark "$VENV/python" benchmarks/bench.py --check
else
  skip_stage benchmark "not yet built"
fi

rm -rf "$SIM_TMP"

# --- summary ---------------------------------------------------------------------------------
echo
echo "----------------------------------------"
echo "PipetteC verify summary"
echo "----------------------------------------"
for stage in ruff mypy pytest simulate benchmark; do
  printf "  %-10s %s\n" "$stage" "${STATUS[$stage]:-?}"
done
echo "----------------------------------------"

if [[ ${#FAILED[@]} -eq 0 ]]; then
  echo "VERIFY: ALL PASS"
  exit 0
else
  echo "VERIFY: FAILED ($(IFS=,; echo "${FAILED[*]}"))"
  exit 1
fi
