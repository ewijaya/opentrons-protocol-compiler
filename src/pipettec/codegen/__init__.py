"""Code generator: :class:`~pipettec.ir.TransferGraph` -> Opentrons API v2 OT-2 Python.

Output is deterministic (stable ordering, fixed apiLevel) so snapshot diffs are meaningful.
"""

from pipettec.codegen.emit import generate

__all__ = ["generate"]
