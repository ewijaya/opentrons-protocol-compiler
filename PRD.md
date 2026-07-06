# PRD — PipetteC execution plan (built to run with `/goal`)

This is the **execution** document. It tells Claude Code exactly what to build, in what
order, and — critically — how to *prove* each piece is done in a way the `/goal` evaluator
can see. For the *why*, scope rationale, architecture, and prior-art positioning, read
[`PROJECT.md`](./PROJECT.md); this PRD does not repeat it.

---

## How to run this

Paste this as your goal condition (it starts a turn immediately and keeps working until met):

```text
/goal Execute PRD.md end to end. DONE when: (1) running `bash scripts/verify.sh` prints the line "VERIFY: ALL PASS" and exits 0, with that output visible in the transcript; (2) every checkbox in PRD.md "Definition of Done" is checked; (3) work is committed and pushed to origin/main with a clean `git status`. CONSTRAINTS that must hold the whole way: opentrons stays pinned >=8.8,<9 (8.8.2); never commit .venv or .claude; every generated example protocol must pass the real `opentrons_simulate` (exit 0 — never skipped, mocked, or stubbed); keep the honest prior-art positioning (no algorithmic-novelty claims); tests must genuinely pass (no xfail/skip to force green). Run `bash scripts/verify.sh` and show its full summary at the END of every turn so this condition is checkable. If not met, keep going. Stop after 45 turns and summarize what remains.
```

Recommended: enable **auto mode** so each goal turn runs unattended.

### Why the goal is shaped this way

The evaluator is a fast model that judges only what's in the conversation — it does not run
commands or open files. Therefore **all "done" signals collapse into one command**,
`scripts/verify.sh`, which runs the whole quality gate and prints a single machine-readable
summary line. Claude must run it and surface the output every turn. Everything below exists to
make that one command trustworthy.

---

## Operating rules (hold these on every turn)

1. **The pin is law.** `opentrons>=8.8,<9` (8.8.2). 9.x cannot simulate OT-2. Never bump it.
2. **The simulator is the source of truth.** A protocol is only "correct" if the real
   `opentrons_simulate` exits 0 on it. Never mock, stub, monkeypatch, or `skip` the simulator
   to get green. If a generated protocol fails to simulate, fix the codegen — not the test.
3. **No green-washing.** No `pytest.mark.skip`/`xfail`, no deleted assertions, no lowered
   thresholds to force a pass. If a criterion can't be met, leave its box unchecked and say so.
4. **Honest positioning stays.** The tip optimization *applies* the published CVRP/LP work; it
   is not presented as novel. Passes cite the source in a docstring. See `PROJECT.md` → Prior Art.
5. **Repo hygiene.** `.venv/` and `.claude/` are git-ignored and must never be committed.
   Commit in logical increments with conventional messages; push to `origin/main`.
6. **Determinism.** Codegen output is stable (sorted, seeded) so snapshot diffs are meaningful.
7. **Work milestone by milestone**, in order. Do not start Mn+1 until Mn's DoD boxes are checked
   and `scripts/verify.sh` is green for everything built so far.
8. **Surface the gate.** End every working turn by running `bash scripts/verify.sh` and pasting
   its summary, so the goal condition is always evaluable.

---

## The verification harness (build this FIRST — it is the spine of `/goal`)

Create `scripts/verify.sh` in the very first turn (task S0). It grows as milestones land, but its
**contract is fixed from day one**:

- Runs the full local gate: `ruff check`, `mypy src`, `pytest --cov` (with the coverage gate),
  then compiles **every** file in `examples/` and runs `opentrons_simulate` on each generated
  protocol asserting exit 0, then runs the benchmark.
- Uses the project `.venv` (Python 3.12, opentrons 8.8.2).
- Prints a per-stage `PASS`/`FAIL` table, then exactly one final line:
  - `VERIFY: ALL PASS` and exits 0 when every stage passes, or
  - `VERIFY: FAILED (<stage>, <stage>...)` and exits 1 otherwise.
- Any stage that has nothing to check yet (early milestones) prints `SKIP (not yet built)` and
  does **not** count as a failure — but the simulator and test stages must never be auto-skipped
  once examples exist.

The final `VERIFY:` line is the single string the `/goal` evaluator keys on. Keep it exact.

---

## Environment (assumed already set up; recreate if missing)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"      # after pyproject exists; pins opentrons>=8.8,<9
```

`pyproject.toml` declares runtime deps (`opentrons>=8.8,<9`, `pyyaml`/`pydantic`, `matplotlib`)
and a `dev` extra (`pytest`, `pytest-cov`, `hypothesis`, `ruff`, `mypy`). Console entry point
`pipettec = pipettec.cli:main`.

---

## Execution plan

Each task lists **Deliverables** and a **Definition of Done (DoD)** — concrete, checkable boxes.
Milestones mirror `PROJECT.md`; this section is the actionable breakdown.

### S0 — Scaffold & harness *(do this first, single turn if possible)*

**Deliverables**
- `pyproject.toml` (deps + dev extra + entry point + ruff/mypy/pytest config, coverage gate 85% on `src`).
- `src/pipettec/` package skeleton: `spec/ ir/ passes/ validate/ codegen/ report/ render/ cli.py`
  (stub modules with typed signatures + docstrings).
- `scripts/verify.sh` implementing the contract above (stages may `SKIP` until built).
- `.github/workflows/ci.yml` running `bash scripts/verify.sh` on push/PR (Python 3.12, installs `.[dev]`).
- `tests/` dir with one trivial passing test so the pytest stage is real from the start.

**DoD**
- [ ] `bash scripts/verify.sh` runs and prints `VERIFY: ALL PASS` (with build stages SKIP-ping).
- [ ] `pip install -e ".[dev]"` succeeds; `pipettec --help` runs.
- [ ] CI workflow present and references `scripts/verify.sh`.

### M1 — Vertical slice: serial dilution → simulator-green

**Deliverables**
- `ir/`: the `TransferGraph` dataclasses (resources, transfers, tip-classes) per `PROJECT.md`.
- `spec/yaml.py`: parse + validate the `serial_dilution` YAML template → lowered `TransferGraph`.
- `passes/tip_reuse.py`: the first optimization pass (docstring cites the CVRP/LP source).
- `validate/`: minimal validator (capacity + tip-exhaustion) with structured diagnostics.
- `codegen/`: `TransferGraph` → deterministic Opentrons API v2 OT-2 Python (`apiLevel` ~2.15).
- `cli.py`: `pipettec compile <spec> -o <out.py> [--report] [--no-optimize]`.
- `examples/dose_response.yaml`.
- Tests: unit (parse, tip_reuse reduces tips + preserves delivery-equivalence), one snapshot,
  first Hypothesis property (valid spec → simulates), integration (CLI → simulate exit 0).

**DoD**
- [ ] `pipettec compile examples/dose_response.yaml -o /tmp/dr.py` then `opentrons_simulate /tmp/dr.py` exits 0.
- [ ] Tip-reuse pass reduces tip count vs `--no-optimize` on the example (assert in a test).
- [ ] Delivery-equivalence property holds over ≥100 generated specs (raise to ≥500 by M5).
- [ ] `scripts/verify.sh` compiles+simulates the example and stays `VERIFY: ALL PASS`.

### M2 — Echo picklist front-end + full optimization suite + metrics

**Deliverables**
- `spec/echo.py`: tolerant Echo picklist CSV reader (column-name variants) → `cherry_pick` IR,
  then the full optimizer runs on it.
- `passes/`: `multichannel_pack.py`, `source_reorder.py`, `reagent_batch.py`.
- `report/metrics.py` + `benchmarks/bench.py`: emit the naive-vs-optimized table (tips,
  aspirations/steps, est. time) from one IR; committed script regenerates the README table.
- `examples/picklist.csv` (textbook, not proprietary).
- Tests: picklist round-trip (CSV → optimized protocol → simulate exit 0); each pass has a
  unit test (reduces its metric AND preserves delivery-equivalence).

**DoD**
- [ ] `pipettec compile examples/picklist.csv -o /tmp/pk.py` → `opentrons_simulate` exits 0.
- [ ] `python benchmarks/bench.py` prints a naive-vs-optimized table; tip reduction ≥60% on the dose-response benchmark.
- [ ] Each of the 4 passes has a passing metric+equivalence test.
- [ ] `scripts/verify.sh` runs the benchmark stage and stays green.

### M3 — Breadth: remaining templates

**Deliverables**
- `spec/` lowerings for `plate_normalization`, `cherry_pick`, `reformat_96_to_384`, `pcr_setup`
  (reuse passes/validator/codegen).
- One `examples/*.yaml` per template.
- Property tests fuzz across **all** templates → every generated protocol simulates cleanly.

**DoD**
- [ ] All 5 templates compile; `opentrons_simulate` exits 0 for every `examples/*` (checked by verify.sh looping the folder).
- [ ] Property suite covers all templates; ≥500 valid specs simulate.

### M4 — Static validator with friendly diagnostics

**Deliverables**
- All 5 rejection classes: volume>capacity, empty/undefined source, tip-exhaustion,
  deck-collision/duplicate-slot/missing-labware, unsafe-tip-reuse contamination.
- Structured diagnostic objects (`code`, `message`, offending element); non-zero CLI exit on reject.
- `examples/bad/*` gallery: one intentionally-invalid spec per class.
- Tests: each bad spec is rejected with the right code and a readable message (never a crash,
  never a protocol emitted); invalid-spec property (fuzzed invalids always rejected cleanly).

**DoD**
- [ ] Each of 5 rejection classes has a bad-spec example rejected with a clear message + non-zero exit.
- [ ] Invalid-spec property holds over ≥500 generated invalid specs.

### M5 — Visuals, cost report, README, polish

**Deliverables**
- `render/`: deck-layout SVG + plate-map heatmap (matplotlib) per example.
- `report/`: full resource/cost report (tips, reagent volume per source, est. wall-clock —
  labelled a model estimate).
- `tests/corpus/`: a few published OT-2 protocols simulate under the pinned version (env sanity).
- **`README.md`**: pitch + auto-generated metrics table + a rendered deck diagram + the
  "what this demonstrates" table + a "Prior Art & how this differs" section (cites Roboliq,
  CVRP/LP tip papers, PyLabRobot). Legible to a non-lab reader in under a minute.

**DoD**
- [ ] Deck SVG + plate heatmap generated for ≥ the flagship example and embedded in README.
- [ ] README opens with pitch + metrics table + deck image + demonstrates-table + Prior Art section.
- [ ] Corpus test green; coverage ≥85% on `src`.
- [ ] Fresh-clone reproducibility: README's documented steps produce a green `scripts/verify.sh`.

---

## Definition of Done (the master gate the goal maps to)

The project is complete when **all** boxes hold and `scripts/verify.sh` prints `VERIFY: ALL PASS`.

**Correctness**
- [ ] Every `examples/*` (and `examples/bad/*` as rejections) is exercised by `scripts/verify.sh`.
- [ ] Every generated example protocol passes real `opentrons_simulate` (exit 0), enforced in CI.
- [ ] Delivery-equivalence property: ≥500 specs, zero counterexamples.
- [ ] Valid-spec property: ≥500 specs all simulate cleanly.
- [ ] Invalid-spec property: ≥500 invalid specs all rejected with structured diagnostics, no crash.
- [ ] Per-template output snapshots pinned; unintended codegen change fails CI.

**Optimization (applied, benchmarked, cited)**
- [ ] `benchmarks/bench.py` emits the naive-vs-optimized table from one IR (tips, steps, est. time).
- [ ] Tip reduction ≥60% (target ~75%) on the dose-response benchmark.
- [ ] Each pass: unit test proving it reduces its metric AND preserves the invariant.
- [ ] Tip-saving passes cite the CVRP/LP formulation in code + docs; no novelty claimed.

**Coverage**
- [ ] All 5 templates compile & simulate.
- [ ] Echo picklist round-trip simulates.
- [ ] All 5 validator rejection classes implemented + tested.

**Engineering & presentation**
- [ ] `scripts/verify.sh` = `ruff` + `mypy` + `pytest --cov` + simulate-all-examples + benchmark, prints `VERIFY: ALL PASS`.
- [ ] Coverage ≥85% on `src`.
- [ ] CI green on GitHub Actions running the same verify script.
- [ ] CLI (`compile`, `validate`, `report`, `render`) documented via `--help` + integration-tested.
- [ ] Visuals generated + embedded in README.
- [ ] README legible to a non-lab recruiter in <1 min; carries the Prior Art section.
- [ ] Fresh clone → documented setup → `scripts/verify.sh` green.

**Delivery**
- [ ] All work committed in logical increments (conventional messages) and pushed to `origin/main`.
- [ ] `git status` clean; `.venv`/`.claude` never committed.
- [ ] `opentrons` still pinned `>=8.8,<9`.

---

## Guardrails recap (do NOT violate)

- Don't bump `opentrons` past `<9`. Don't commit `.venv`/`.claude`.
- Don't fake the simulator or skip tests to force green. Fix the generator instead.
- Don't claim algorithmic novelty. Cite prior art.
- Don't hand-edit the README metrics table — regenerate it from `benchmarks/bench.py`.
- If genuinely blocked on a criterion, leave its box unchecked, explain why in the turn, and
  continue with the rest rather than stalling the whole goal.
