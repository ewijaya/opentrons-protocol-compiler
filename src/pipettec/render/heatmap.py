"""Render a plate-map heatmap (total dispensed volume per well) as a PNG via matplotlib."""

from __future__ import annotations

from pathlib import Path

from pipettec.ir import TransferGraph
from pipettec.labware_defs import LABWARE


def render_plate_heatmap(graph: TransferGraph, out_path: str | Path, plate_id: str | None = None) -> Path:
    """Write a PNG heatmap of per-well dispensed volume for one destination plate.

    Picks the plate that receives the most transfers if ``plate_id`` is not given.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    # Choose the destination plate.
    if plate_id is None:
        counts: dict[str, int] = {}
        for t in graph.transfers:
            counts[t.dest_labware] = counts.get(t.dest_labware, 0) + 1
        if not counts:
            raise ValueError("no transfers to render")
        plate_id = max(counts, key=lambda k: counts[k])

    lw = graph.labware_by_id(plate_id)
    ldef = LABWARE[lw.load_name]
    grid = np.zeros((ldef.n_rows, ldef.n_cols))
    row_index = {r: i for i, r in enumerate(ldef.rows)}
    for t in graph.transfers:
        if t.dest_labware != plate_id:
            continue
        r = t.dest_well[0]
        c = int(t.dest_well[1:])
        if r in row_index and 1 <= c <= ldef.n_cols:
            grid[row_index[r], c - 1] += t.volume

    fig, ax = plt.subplots(figsize=(max(6, ldef.n_cols * 0.5), max(3, ldef.n_rows * 0.5)))
    im = ax.imshow(grid, cmap="viridis", aspect="equal")
    ax.set_xticks(range(ldef.n_cols))
    ax.set_xticklabels([str(c) for c in range(1, ldef.n_cols + 1)], fontsize=7)
    ax.set_yticks(range(ldef.n_rows))
    ax.set_yticklabels(list(ldef.rows), fontsize=7)
    ax.set_title(f"{graph.metadata.get('name', 'protocol')} — dispensed uL on {plate_id}")
    fig.colorbar(im, ax=ax, label="uL", shrink=0.8)
    fig.tight_layout()
    out = Path(out_path)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out
