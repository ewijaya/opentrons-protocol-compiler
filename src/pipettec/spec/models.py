"""Pydantic schema for the YAML spec front-end.

Each template is a distinct model with clear field validation; malformed specs raise a
``pydantic.ValidationError`` which the CLI reports readably. Templates lower onto the shared IR
in :mod:`pipettec.spec.templates`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SerialDilution(BaseModel):
    """Dose–response serial dilution: N points diluted by ``factor`` across a plate row block."""

    template: Literal["serial_dilution"]
    compounds: list[str] = Field(min_length=1)
    points: int = Field(ge=2, le=12)
    replicates: int = Field(default=1, ge=1, le=8)
    top_conc_uM: float = Field(gt=0)
    factor: float = Field(gt=1)
    diluent: str = "DMSO"
    transfer_volume_ul: float = Field(default=50.0, gt=0)
    name: str = "serial_dilution"


class PlateNormalization(BaseModel):
    """Normalize a set of wells to a common target volume by adding diluent."""

    template: Literal["plate_normalization"]
    wells: list[str] = Field(min_length=1)
    current_volume_ul: list[float] = Field(min_length=1)
    target_volume_ul: float = Field(gt=0)
    diluent: str = "buffer"
    name: str = "plate_normalization"

    @field_validator("current_volume_ul")
    @classmethod
    def _same_length(cls, v: list[float], info):  # type: ignore[no-untyped-def]
        wells = info.data.get("wells")
        if wells is not None and len(v) != len(wells):
            raise ValueError("current_volume_ul must match wells length")
        return v


class CherryPick(BaseModel):
    """Arbitrary source->dest transfers (also the Echo picklist lowering target)."""

    template: Literal["cherry_pick"]
    transfers: list[dict] = Field(min_length=1)  # {source, dest, volume}
    name: str = "cherry_pick"


class Reformat96to384(BaseModel):
    """Consolidate four 96-well quadrants into one 384-well plate."""

    template: Literal["reformat_96_to_384"]
    source_plates: list[str] = Field(min_length=1, max_length=4)
    volume_ul: float = Field(default=10.0, gt=0)
    name: str = "reformat_96_to_384"


class PcrSetup(BaseModel):
    """Distribute mastermix + add template per reaction well."""

    template: Literal["pcr_setup"]
    reactions: int = Field(ge=1, le=96)
    mastermix_volume_ul: float = Field(default=18.0, gt=0)
    template_volume_ul: float = Field(default=2.0, gt=0)
    name: str = "pcr_setup"


SPEC_MODELS = {
    "serial_dilution": SerialDilution,
    "plate_normalization": PlateNormalization,
    "cherry_pick": CherryPick,
    "reformat_96_to_384": Reformat96to384,
    "pcr_setup": PcrSetup,
}
