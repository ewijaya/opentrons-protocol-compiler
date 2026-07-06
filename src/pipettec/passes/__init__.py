"""Optimization passes over the ``TransferGraph`` IR.

Every pass is a pure function ``TransferGraph -> TransferGraph`` that preserves
delivery-equivalence (same total volume per ``(source, dest)`` pair) and contamination-safety
(a tip is shared only within one tip class). The pipeline runs them in a fixed order.

The tip-saving passes *apply* the published operations-research formulation of liquid handling
as a capacitated vehicle-routing / linear-programming problem — they do not invent it. See the
per-pass docstrings for citations (NAR Genomics & Bioinformatics 2022; Digital Discovery 2025).
"""

from pipettec.passes.multichannel_pack import multichannel_pack
from pipettec.passes.pipeline import optimize
from pipettec.passes.reagent_batch import reagent_batch
from pipettec.passes.source_reorder import source_reorder
from pipettec.passes.tip_reuse import tip_reuse

__all__ = [
    "optimize",
    "tip_reuse",
    "multichannel_pack",
    "source_reorder",
    "reagent_batch",
]
