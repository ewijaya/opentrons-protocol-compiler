"""The intermediate representation: :class:`TransferGraph` and its parts.

Every front-end lowers to a :class:`TransferGraph`; every optimization pass rewrites one;
codegen walks one. Passes never touch YAML or Python text — only this IR.
"""

from pipettec.ir.graph import (
    Instrument,
    Labware,
    TipClass,
    Transfer,
    TransferGraph,
)

__all__ = [
    "Instrument",
    "Labware",
    "TipClass",
    "Transfer",
    "TransferGraph",
]
