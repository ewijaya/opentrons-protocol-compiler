"""PipetteC — a compiler for liquid-handling protocols.

Compiles a high-level experiment spec (YAML template or Echo picklist CSV) into a
validated, tip-optimized Opentrons OT-2 Python protocol via a real compiler pipeline:

    spec -> TransferGraph IR -> optimization passes -> static validator -> codegen -> protocol.py

See PROJECT.md for scope and architecture; PRD.md for the execution plan.
"""

__version__ = "0.1.0"
