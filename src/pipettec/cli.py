"""PipetteC command-line interface.

Subcommands:

* ``compile <spec> -o <out.py> [--no-optimize] [--report]`` — compile a spec to a protocol.
* ``validate <spec>`` — run the validator; non-zero exit + diagnostics on rejection.
* ``report <spec>`` — print the naive-vs-optimized metrics table.
* ``render <spec> --deck <svg> [--heatmap <png>]`` — write deck SVG / plate heatmap.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipettec import __version__
from pipettec.compiler import compile_spec, front_end_for
from pipettec.passes import optimize
from pipettec.report import format_comparison_markdown, format_report
from pipettec.spec.yaml_spec import SpecError
from pipettec.validate import ValidationError, validate


def _err(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def cmd_compile(args: argparse.Namespace) -> int:
    try:
        final, code = compile_spec(args.spec, do_optimize=not args.no_optimize)
    except (SpecError, ValueError) as e:
        return _err(str(e))
    except ValidationError as e:
        print("validation failed:", file=sys.stderr)
        for d in e.diagnostics:
            print(f"  - {d}", file=sys.stderr)
        return 1
    Path(args.out).write_text(code)
    if args.report:
        naive = front_end_for(args.spec)
        opt = optimize(front_end_for(args.spec))
        print(format_comparison_markdown(naive, opt))
    print(f"wrote {args.out}  (tips={final.tip_count()}, transfers={len(final.transfers)})")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        graph = optimize(front_end_for(args.spec)) if not args.no_optimize else front_end_for(args.spec)
        validate(graph)
    except (SpecError, ValueError) as e:
        return _err(str(e))
    except ValidationError as e:
        print("INVALID:", file=sys.stderr)
        for d in e.diagnostics:
            print(f"  - {d}", file=sys.stderr)
        return 1
    print("VALID")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        naive = front_end_for(args.spec)
        opt = optimize(front_end_for(args.spec))
    except (SpecError, ValueError) as e:
        return _err(str(e))
    print(format_report(opt))
    print()
    print(format_comparison_markdown(naive, opt))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    from pipettec.render import render_deck_svg, render_plate_heatmap

    try:
        graph = optimize(front_end_for(args.spec))
    except (SpecError, ValueError) as e:
        return _err(str(e))
    if args.deck:
        Path(args.deck).write_text(render_deck_svg(graph, graph.metadata.get("name", "")))
        print(f"wrote {args.deck}")
    if args.heatmap:
        render_plate_heatmap(graph, args.heatmap)
        print(f"wrote {args.heatmap}")
    if not args.deck and not args.heatmap:
        return _err("nothing to render: pass --deck and/or --heatmap")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipettec", description="Compile liquid-handling specs to Opentrons OT-2 protocols.")
    p.add_argument("--version", action="version", version=f"pipettec {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("compile", help="compile a spec to an OT-2 protocol")
    c.add_argument("spec")
    c.add_argument("-o", "--out", required=True, help="output protocol.py path")
    c.add_argument("--no-optimize", action="store_true", help="emit the naive (unoptimized) protocol")
    c.add_argument("--report", action="store_true", help="print the naive-vs-optimized metrics table")
    c.set_defaults(func=cmd_compile)

    v = sub.add_parser("validate", help="validate a spec; non-zero exit on rejection")
    v.add_argument("spec")
    v.add_argument("--no-optimize", action="store_true")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("report", help="print the resource + before/after metrics")
    r.add_argument("spec")
    r.set_defaults(func=cmd_report)

    rn = sub.add_parser("render", help="render deck SVG and/or plate heatmap")
    rn.add_argument("spec")
    rn.add_argument("--deck", help="output deck SVG path")
    rn.add_argument("--heatmap", help="output plate heatmap PNG path")
    rn.set_defaults(func=cmd_render)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
