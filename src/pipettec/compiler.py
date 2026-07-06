"""End-to-end compile driver tying the pipeline stages together.

    spec file -> TransferGraph -> [optimize] -> validate -> codegen -> protocol.py text
"""

from __future__ import annotations

from pathlib import Path

from pipettec.codegen import generate
from pipettec.ir import TransferGraph
from pipettec.passes import optimize
from pipettec.spec import load_echo_csv, load_yaml
from pipettec.validate import validate


def front_end_for(path: str | Path) -> TransferGraph:
    """Dispatch to the right front-end by file extension."""
    p = Path(path)
    if p.suffix.lower() in (".yaml", ".yml"):
        return load_yaml(p)
    if p.suffix.lower() == ".csv":
        return load_echo_csv(p)
    raise ValueError(f"unsupported spec extension: {p.suffix!r} (use .yaml/.yml or .csv)")


def compile_spec(path: str | Path, do_optimize: bool = True) -> tuple[TransferGraph, str]:
    """Compile a spec file to (final IR, protocol.py text). Validates before codegen."""
    graph = front_end_for(path)
    final = optimize(graph) if do_optimize else graph
    validate(final)
    code = generate(final)
    return final, code
