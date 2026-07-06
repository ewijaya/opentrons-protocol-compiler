"""The static validator.

Runs on a :class:`~pipettec.ir.TransferGraph` after optimization, before codegen. Collects
every problem it can find (so users see all issues at once) and raises a
:class:`ValidationError` carrying structured :class:`Diagnostic` objects if any error is found.

The five rejection classes:

* ``capacity`` — a transfer volume exceeds the pipette tip range or a well's max volume.
* ``empty-source`` — a transfer aspirates from a well that is never filled and is not a
  declared reagent source.
* ``tip-exhaustion`` — an instrument needs more tips than its loaded racks provide.
* ``deck-collision`` — two labware share a slot, or a transfer/instrument references missing
  labware.
* ``contamination`` — a tip group spans more than one tip class (unsafe reuse).
"""

from __future__ import annotations

from pipettec.ir import TransferGraph
from pipettec.labware_defs import LABWARE, PIPETTES, tiprack_capacity
from pipettec.validate.diagnostics import (
    CAPACITY,
    CONTAMINATION,
    DECK_COLLISION,
    EMPTY_SOURCE,
    TIP_EXHAUSTION,
    Diagnostic,
    ValidationError,
)


def validate(graph: TransferGraph) -> None:
    """Validate ``graph``; raise :class:`ValidationError` with all diagnostics if invalid."""
    diags: list[Diagnostic] = []
    diags += _check_deck(graph)
    # If the deck itself is malformed (missing labware), downstream checks can't trust
    # labware lookups; report deck problems and stop before dereferencing them.
    if any(d.code == DECK_COLLISION for d in diags):
        raise ValidationError(diags)
    diags += _check_capacity(graph)
    diags += _check_empty_source(graph)
    diags += _check_tip_exhaustion(graph)
    diags += _check_contamination(graph)
    if diags:
        raise ValidationError(diags)


def _check_deck(graph: TransferGraph) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    seen_slots: dict[str, str] = {}
    known_ids: set[str] = set()
    for lw in graph.labware:
        known_ids.add(lw.id)
        if lw.load_name not in LABWARE:
            diags.append(
                Diagnostic(DECK_COLLISION, f"unknown labware load name {lw.load_name!r}", lw.id)
            )
        if lw.slot in seen_slots:
            diags.append(
                Diagnostic(
                    DECK_COLLISION,
                    f"slot {lw.slot} assigned to both {seen_slots[lw.slot]!r} and {lw.id!r}",
                    lw.id,
                )
            )
        else:
            seen_slots[lw.slot] = lw.id
    # Instruments must reference existing tip racks.
    for inst in graph.instruments:
        for tr in inst.tip_racks:
            if tr not in known_ids:
                diags.append(
                    Diagnostic(DECK_COLLISION, f"instrument references missing tip rack {tr!r}", inst.id)
                )
    # Transfers must reference existing labware and instruments.
    inst_ids = {i.id for i in graph.instruments}
    for t in graph.transfers:
        for lid in (t.source_labware, t.dest_labware):
            if lid not in known_ids:
                diags.append(
                    Diagnostic(DECK_COLLISION, f"transfer references missing labware {lid!r}", f"{t.source}->{t.dest}")
                )
        if t.instrument not in inst_ids:
            diags.append(
                Diagnostic(DECK_COLLISION, f"transfer references missing instrument {t.instrument!r}", f"{t.source}->{t.dest}")
            )
    return diags


def _check_capacity(graph: TransferGraph) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    for t in graph.transfers:
        inst = graph.instrument_by_id(t.instrument)
        pdef = PIPETTES.get(inst.model)
        max_ul = pdef.max_ul if pdef else inst.max_volume_ul
        min_ul = pdef.min_ul if pdef else inst.min_volume_ul
        if t.volume > max_ul + 1e-9:
            diags.append(
                Diagnostic(
                    CAPACITY,
                    f"volume {t.volume}uL exceeds {inst.model} max {max_ul}uL",
                    f"{t.source}->{t.dest}",
                )
            )
        if t.volume < min_ul - 1e-9:
            diags.append(
                Diagnostic(
                    CAPACITY,
                    f"volume {t.volume}uL below {inst.model} min {min_ul}uL",
                    f"{t.source}->{t.dest}",
                )
            )
    # Cumulative volume into a dest well must not exceed its capacity.
    dest_totals: dict[str, float] = {}
    for t in graph.transfers:
        dest_totals[t.dest] = dest_totals.get(t.dest, 0.0) + t.volume
    for dest, total in dest_totals.items():
        lid, _ = dest.split(":", 1)
        lw = graph.labware_by_id(lid)
        ldef = LABWARE[lw.load_name]
        if total > ldef.well_max_ul + 1e-9:
            diags.append(
                Diagnostic(
                    CAPACITY,
                    f"cumulative {round(total, 3)}uL into well exceeds capacity {ldef.well_max_ul}uL",
                    dest,
                )
            )
    return diags


def _check_empty_source(graph: TransferGraph) -> list[Diagnostic]:
    """Flag aspiration from a well that should have been filled but never was.

    A source well is valid if any of the following holds:

    * it is a reservoir / reagent trough (operator pre-fills these);
    * it is on a labware that only ever acts as a source and never a destination (a dedicated
      *input* plate the operator loads externally — e.g. a stamp/source plate);
    * it is filled by some transfer in this protocol (it is some transfer's dest).

    The genuine error we catch is a *working* plate (used as both source and dest) where a
    specific well is aspirated from but never filled — an on-deck data dependency violation.
    """
    filled: set[str] = {t.dest for t in graph.transfers}
    dest_labware: set[str] = {t.dest_labware for t in graph.transfers}
    reservoir_labware = {
        lw.id
        for lw in graph.labware
        if LABWARE[lw.load_name].n_rows == 1 and not LABWARE[lw.load_name].is_tiprack
    }
    diags: list[Diagnostic] = []
    for t in graph.transfers:
        if t.source_labware in reservoir_labware:
            continue
        # Dedicated input plate (never a destination in this protocol): operator pre-fills it.
        if t.source_labware not in dest_labware:
            continue
        if t.source not in filled:
            diags.append(
                Diagnostic(EMPTY_SOURCE, "aspirate from never-filled source well", t.source)
            )
    return diags


def _check_tip_exhaustion(graph: TransferGraph) -> list[Diagnostic]:
    diags: list[Diagnostic] = []
    # Tips needed per instrument.
    from collections import defaultdict

    needed: dict[str, int] = defaultdict(int)
    counted_tip_groups: dict[str, set[int]] = defaultdict(set)
    counted_channel_groups: dict[str, set[int]] = defaultdict(set)
    for t in graph.transfers:
        if t.tip_group is not None:
            if t.tip_group not in counted_tip_groups[t.instrument]:
                counted_tip_groups[t.instrument].add(t.tip_group)
                needed[t.instrument] += 1
            continue
        if t.channel_group is not None:
            if t.channel_group not in counted_channel_groups[t.instrument]:
                counted_channel_groups[t.instrument].add(t.channel_group)
                needed[t.instrument] += 1
            continue
        needed[t.instrument] += 1
    for inst in graph.instruments:
        capacity = sum(tiprack_capacity(graph.labware_by_id(tr).load_name) for tr in inst.tip_racks)
        if needed.get(inst.id, 0) > capacity:
            diags.append(
                Diagnostic(
                    TIP_EXHAUSTION,
                    f"{inst.id} needs {needed[inst.id]} tips but only {capacity} loaded",
                    inst.id,
                )
            )
    return diags


def _check_contamination(graph: TransferGraph) -> list[Diagnostic]:
    """A tip group may span only one tip class (else it is unsafe reuse)."""
    diags: list[Diagnostic] = []
    group_classes: dict[int, set[str]] = {}
    for t in graph.transfers:
        if t.tip_group is None:
            continue
        group_classes.setdefault(t.tip_group, set()).add(t.tip_class)
    for gid, classes in group_classes.items():
        if len(classes) > 1:
            diags.append(
                Diagnostic(
                    CONTAMINATION,
                    f"tip group {gid} reused across distinct tip classes {sorted(classes)}",
                    f"group={gid}",
                )
            )
    return diags
