"""Static validator: reject impossible or unsafe specs before any robot would move.

Runs on the IR *after* optimization and *before* codegen. Emits structured
:class:`Diagnostic` objects and raises :class:`ValidationError` on any error.
"""

from pipettec.validate.diagnostics import Diagnostic, ValidationError
from pipettec.validate.validator import validate

__all__ = ["Diagnostic", "ValidationError", "validate"]
