"""Render the OT-2 deck layout as a standalone SVG (no external deps, deterministic).

The OT-2 deck is a 3-column x 4-row grid of slots numbered 1..11 (slot 12 is the fixed trash).
We draw each occupied slot with its labware id and load name, colour-coded by kind.
"""

from __future__ import annotations

from pipettec.ir import TransferGraph
from pipettec.labware_defs import LABWARE

# Slot -> (col, row) with row 0 at the *bottom* (matching the physical OT-2 layout).
_SLOT_GRID = {
    "1": (0, 0), "2": (1, 0), "3": (2, 0),
    "4": (0, 1), "5": (1, 1), "6": (2, 1),
    "7": (0, 2), "8": (1, 2), "9": (2, 2),
    "10": (0, 3), "11": (1, 3), "12": (2, 3),
}

_W, _H = 150, 100  # slot size
_PAD = 20


def _kind_color(load_name: str) -> str:
    d = LABWARE.get(load_name)
    if d is None:
        return "#dddddd"
    if d.is_tiprack:
        return "#ffe08a"  # amber tips
    if d.n_rows == 1:
        return "#a8d8ea"  # blue reservoir
    return "#c8e6c9"  # green plate


def render_deck_svg(graph: TransferGraph, title: str = "") -> str:
    """Return an SVG string of the deck for ``graph``."""
    by_slot = {lw.slot: lw for lw in graph.labware}
    grid_w = 3 * _W + 4 * _PAD
    grid_h = 4 * _H + 5 * _PAD + 30
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{grid_w}" height="{grid_h}" '
        f'viewBox="0 0 {grid_w} {grid_h}" font-family="sans-serif">'
    )
    parts.append(f'<rect width="{grid_w}" height="{grid_h}" fill="#fafafa"/>')
    if title:
        parts.append(
            f'<text x="{grid_w / 2}" y="20" text-anchor="middle" font-size="16" '
            f'font-weight="bold">{_esc(title)}</text>'
        )
    # Fixed trash label on slot 12.
    trash = {"12": "Fixed Trash"}
    for slot, (col, row) in _SLOT_GRID.items():
        x = _PAD + col * (_W + _PAD)
        y = 30 + (3 - row) * (_H + _PAD) + _PAD
        lw = by_slot.get(slot)
        fill = _kind_color(lw.load_name) if lw else ("#eeeeee" if slot != "12" else "#f0c0c0")
        parts.append(
            f'<rect x="{x}" y="{y}" width="{_W}" height="{_H}" rx="8" fill="{fill}" '
            f'stroke="#555" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{x + 6}" y="{y + 16}" font-size="11" fill="#333">slot {slot}</text>'
        )
        if lw:
            parts.append(
                f'<text x="{x + _W / 2}" y="{y + _H / 2}" text-anchor="middle" '
                f'font-size="13" font-weight="bold">{_esc(lw.id)}</text>'
            )
            parts.append(
                f'<text x="{x + _W / 2}" y="{y + _H / 2 + 16}" text-anchor="middle" '
                f'font-size="9" fill="#444">{_esc(lw.load_name)}</text>'
            )
        elif slot in trash:
            parts.append(
                f'<text x="{x + _W / 2}" y="{y + _H / 2}" text-anchor="middle" '
                f'font-size="11" fill="#a33">{trash[slot]}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
