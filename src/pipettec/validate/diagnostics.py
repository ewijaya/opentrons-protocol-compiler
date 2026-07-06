"""Structured diagnostics emitted by the validator.

Each diagnostic carries a stable ``code`` (one of the five rejection classes), a
human-readable ``message``, and the ``offending`` element (a well/labware/transfer repr).
The CLI turns a :class:`ValidationError` into a non-zero exit with a readable report.
"""

from __future__ import annotations

from dataclasses import dataclass

# The five rejection classes (stable codes; referenced by tests and docs).
CAPACITY = "capacity"  # volume exceeds tip or well capacity
EMPTY_SOURCE = "empty-source"  # aspirate from an empty / undefined source
TIP_EXHAUSTION = "tip-exhaustion"  # more tips needed than loaded
DECK_COLLISION = "deck-collision"  # duplicate slot / missing labware
CONTAMINATION = "contamination"  # unsafe tip reuse across tip classes

REJECTION_CLASSES = (CAPACITY, EMPTY_SOURCE, TIP_EXHAUSTION, DECK_COLLISION, CONTAMINATION)


@dataclass(frozen=True)
class Diagnostic:
    """One validation finding."""

    code: str
    message: str
    offending: str = ""

    def __str__(self) -> str:
        loc = f" [{self.offending}]" if self.offending else ""
        return f"{self.code}: {self.message}{loc}"


class ValidationError(Exception):
    """Raised when validation finds one or more errors.

    Carries the full list of :class:`Diagnostic` objects for structured reporting.
    """

    def __init__(self, diagnostics: list[Diagnostic]):
        self.diagnostics = diagnostics
        super().__init__("; ".join(str(d) for d in diagnostics))
