"""The ``TransferGraph`` IR — the single source of truth between front-ends and codegen.

Design notes
------------
* A :class:`Transfer` is one atomic liquid move: aspirate ``volume`` uL from ``source``,
  dispense into ``dest``. Wells are addressed as ``"<labware_id>:<well>"`` (e.g. ``"plate:A1"``).
* ``tip_class`` names an equivalence class of transfers that *may* share a tip without
  violating contamination rules (see :class:`TipClass`). It is the hook the optimizer and
  validator use to reason about safe tip reuse.
* ``tip_group`` is assigned by optimization passes: transfers sharing a non-``None``
  ``tip_group`` are emitted by codegen with a single tip (pick up once, drop once). It is
  ``None`` in a naive (unoptimized) graph — every transfer gets its own tip.
* ``channel_group`` is assigned by the multi-channel packing pass: transfers sharing a
  ``channel_group`` collapse into one 8-channel move in codegen. ``None`` means single-channel.

The graph is intentionally plain dataclasses (not pydantic) so passes can mutate and copy
cheaply; front-ends do the schema validation before building it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class Labware:
    """A plate, tip rack, or reservoir occupying a deck slot.

    ``load_name`` is an Opentrons labware definition name (e.g.
    ``"corning_96_wellplate_360ul_flat"``). ``slot`` is a deck position ``"1"``..``"11"``.
    """

    id: str
    load_name: str
    slot: str
    is_tiprack: bool = False


@dataclass(frozen=True)
class Instrument:
    """A pipette mounted on the OT-2.

    ``model`` is an Opentrons pipette load name (e.g. ``"p300_single_gen2"``).
    ``tip_racks`` lists the labware ids of the tip racks it draws from.
    """

    id: str
    model: str
    mount: str  # "left" | "right"
    tip_racks: tuple[str, ...]
    channels: int = 1  # 1 for single, 8 for multi
    min_volume_ul: float = 1.0
    max_volume_ul: float = 300.0


@dataclass(frozen=True)
class TipClass:
    """An equivalence class declaring which transfers may safely share a tip.

    Two transfers with the same ``name`` are contamination-compatible: e.g. all dispenses of
    one clean reagent from a single source. Reusing a tip across *different* tip classes is a
    contamination violation and is rejected by the validator — never a silent optimization.
    """

    name: str
    description: str = ""


@dataclass(frozen=True)
class Transfer:
    """One atomic aspirate+dispense of ``volume`` uL from ``source`` to ``dest``.

    ``source`` / ``dest`` are ``"<labware_id>:<well>"`` strings. ``tip_class`` names the
    contamination equivalence class. ``tip_group`` / ``channel_group`` are set by passes.
    """

    source: str
    dest: str
    volume: float
    instrument: str
    tip_class: str
    tip_group: int | None = None
    channel_group: int | None = None

    @property
    def source_labware(self) -> str:
        return self.source.split(":", 1)[0]

    @property
    def source_well(self) -> str:
        return self.source.split(":", 1)[1]

    @property
    def dest_labware(self) -> str:
        return self.dest.split(":", 1)[0]

    @property
    def dest_well(self) -> str:
        return self.dest.split(":", 1)[1]


@dataclass
class TransferGraph:
    """The IR: resources + an ordered list of transfers + tip classes.

    ``metadata`` carries protocol-level info (name, description, apiLevel) through to codegen.
    ``optimized`` is a provenance flag flipped by the pass pipeline.
    """

    labware: list[Labware] = field(default_factory=list)
    instruments: list[Instrument] = field(default_factory=list)
    tip_classes: list[TipClass] = field(default_factory=list)
    transfers: list[Transfer] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    optimized: bool = False

    # --- lookups -----------------------------------------------------------------

    def labware_by_id(self, lid: str) -> Labware:
        for lw in self.labware:
            if lw.id == lid:
                return lw
        raise KeyError(f"unknown labware id: {lid!r}")

    def instrument_by_id(self, iid: str) -> Instrument:
        for inst in self.instruments:
            if inst.id == iid:
                return inst
        raise KeyError(f"unknown instrument id: {iid!r}")

    # --- semantics helpers (used by the correctness invariant) -------------------

    def delivery_map(self) -> dict[tuple[str, str], float]:
        """Total volume delivered per ``(source, dest)`` pair.

        This is the observable semantics of the graph: what liquid ends up where. Every
        optimization pass must preserve this map exactly (delivery-equivalence).
        """
        out: dict[tuple[str, str], float] = {}
        for t in self.transfers:
            key = (t.source, t.dest)
            out[key] = round(out.get(key, 0.0) + t.volume, 6)
        return out

    def tip_count(self) -> int:
        """Number of tips consumed when emitted.

        Transfers sharing a non-``None`` ``tip_group`` use one tip; grouped multi-channel
        transfers (same ``channel_group``) share the group's tip pickup. Ungrouped transfers
        each cost one tip.
        """
        seen_tip_groups: set[int] = set()
        seen_channel_groups: set[int] = set()
        count = 0
        for t in self.transfers:
            if t.tip_group is not None:
                if t.tip_group not in seen_tip_groups:
                    seen_tip_groups.add(t.tip_group)
                    count += 1
                continue
            if t.channel_group is not None:
                if t.channel_group not in seen_channel_groups:
                    seen_channel_groups.add(t.channel_group)
                    count += 1
                continue
            count += 1
        return count

    def copy(self) -> TransferGraph:
        """A deep-enough copy: transfers are frozen dataclasses, so a fresh list suffices."""
        return replace(
            self,
            labware=list(self.labware),
            instruments=list(self.instruments),
            tip_classes=list(self.tip_classes),
            transfers=list(self.transfers),
            metadata=dict(self.metadata),
        )
