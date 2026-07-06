"""YAML front-end: parse + schema-validate a spec, then lower it to a ``TransferGraph``."""

from __future__ import annotations

from pathlib import Path

import yaml

from pipettec.ir import TransferGraph
from pipettec.spec.models import SPEC_MODELS
from pipettec.spec.templates import LOWERINGS


class SpecError(Exception):
    """Raised on a malformed or unknown spec (before any IR is built)."""


def load_yaml_str(text: str) -> TransferGraph:
    """Parse a YAML spec string and lower it to a ``TransferGraph``."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SpecError("spec must be a YAML mapping")
    template = data.get("template")
    if template not in SPEC_MODELS:
        raise SpecError(
            f"unknown template {template!r}; expected one of {sorted(SPEC_MODELS)}"
        )
    model_cls = SPEC_MODELS[template]
    spec = model_cls(**data)
    lower = LOWERINGS[template]
    return lower(spec)


def load_yaml(path: str | Path) -> TransferGraph:
    """Load and lower a YAML spec file."""
    text = Path(path).read_text()
    return load_yaml_str(text)
