"""Echo picklist CSV front-end.

The Echo acoustic dispenser's picklist is the de-facto industry format: rows of
``(source well, destination well, transfer volume)``, sometimes with plate-ID columns. Column
names vary across exports, so this reader is tolerant of the common variants.

A picklist lowers to a ``cherry_pick`` TransferGraph and then runs the full optimizer, so a raw
picklist comes out optimized. Echo volumes are in **nanolitres**; we convert nL -> uL. Because
the OT-2 minimum is ~1 uL (p20), sub-microlitre Echo volumes are summed per (source, dest) pair
and rejected by the validator if still below range — we do not silently fabricate volume.
"""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from pipettec.ir import TransferGraph
from pipettec.spec.models import CherryPick
from pipettec.spec.templates import lower_cherry_pick

# Accepted column-name variants (lower-cased, stripped) -> canonical field.
_SOURCE_KEYS = {"source well", "sourcewell", "source", "src well", "source_well"}
_DEST_KEYS = {
    "destination well",
    "destinationwell",
    "dest well",
    "destination",
    "dest",
    "destination_well",
}
_VOL_KEYS = {
    "transfer volume",
    "transfervolume",
    "volume",
    "transfer volume (nl)",
    "volume (nl)",
    "transfer_volume",
}


def _pick(header: list[str], keys: set[str]) -> int:
    for i, h in enumerate(header):
        if h.strip().lower() in keys:
            return i
    raise ValueError(f"picklist missing a column for {sorted(keys)[:1]}...; got {header}")


def load_echo_csv_str(text: str, name: str = "echo_picklist") -> TransferGraph:
    """Parse an Echo picklist CSV string into an optimized-ready cherry_pick graph."""
    reader = csv.reader(StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("empty picklist")
    header = rows[0]
    si = _pick(header, _SOURCE_KEYS)
    di = _pick(header, _DEST_KEYS)
    vi = _pick(header, _VOL_KEYS)

    # Sum nL per (source, dest), then convert to uL — combines split Echo drops into one move.
    from collections import OrderedDict

    totals: OrderedDict[tuple[str, str], float] = OrderedDict()
    for r in rows[1:]:
        src = r[si].strip()
        dst = r[di].strip()
        nl = float(r[vi].strip())
        key = (src, dst)
        totals[key] = totals.get(key, 0.0) + nl

    transfers = [
        {"source": src, "dest": dst, "volume": round(nl / 1000.0, 3)}
        for (src, dst), nl in totals.items()
    ]
    spec = CherryPick(template="cherry_pick", transfers=transfers, name=name)
    return lower_cherry_pick(spec)


def load_echo_csv(path: str | Path, name: str | None = None) -> TransferGraph:
    """Load an Echo picklist CSV file into a cherry_pick graph."""
    p = Path(path)
    return load_echo_csv_str(p.read_text(), name or p.stem)
