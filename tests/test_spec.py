"""Front-end tests: YAML templates and Echo picklist parsing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydError

from pipettec.spec import load_echo_csv, load_yaml_str
from pipettec.spec.echo import load_echo_csv_str
from pipettec.spec.yaml_spec import SpecError


def test_serial_dilution_lowers() -> None:
    g = load_yaml_str(
        "template: serial_dilution\ncompounds: [A]\npoints: 4\nreplicates: 8\n"
        "top_conc_uM: 100\nfactor: 2\ntransfer_volume_ul: 50\n"
    )
    assert g.transfers
    assert any("plate:" in t.dest for t in g.transfers)


def test_unknown_template_rejected() -> None:
    with pytest.raises(SpecError):
        load_yaml_str("template: nope\n")


def test_non_mapping_rejected() -> None:
    with pytest.raises(SpecError):
        load_yaml_str("- 1\n- 2\n")


def test_bad_field_rejected_by_schema() -> None:
    with pytest.raises(PydError):
        # points must be >= 2
        load_yaml_str(
            "template: serial_dilution\ncompounds: [A]\npoints: 1\n"
            "top_conc_uM: 100\nfactor: 2\n"
        )


def test_echo_picklist_column_variants() -> None:
    csv = "Source Well,Destination Well,Transfer Volume\nA1,A1,25000\nA1,A2,25000\n"
    g = load_echo_csv_str(csv)
    # nL -> uL conversion
    assert all(t.volume == 25.0 for t in g.transfers)
    assert len(g.transfers) == 2


def test_echo_picklist_alt_headers() -> None:
    csv = "source,dest,volume\nA1,B1,30000\n"
    g = load_echo_csv_str(csv)
    assert g.transfers[0].volume == 30.0


def test_echo_picklist_sums_split_drops() -> None:
    # Two drops into the same (source,dest) sum into one move.
    csv = "Source Well,Destination Well,Transfer Volume\nA1,A1,10000\nA1,A1,15000\n"
    g = load_echo_csv_str(csv)
    assert len(g.transfers) == 1
    assert g.transfers[0].volume == 25.0


def test_echo_missing_column() -> None:
    with pytest.raises(ValueError):
        load_echo_csv_str("foo,bar\n1,2\n")


def test_echo_file_roundtrip(examples_dir) -> None:
    g = load_echo_csv(examples_dir / "picklist.csv")
    assert g.transfers
