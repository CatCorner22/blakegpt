import csv
from pathlib import Path

import pytest

from tools.oig_exclusion_check import check_names, download_leie, main


def test_matches_exact_name_npi_and_business_from_synthetic_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "leie.csv"
    with fixture.open(encoding="utf-8") as source:
        leie_rows = list(csv.DictReader(source))
    matches = check_names(
        [
            {
                "first": "ADA",
                "last": "sample",
                "npi": "1234567890",
                "business": "sample dental llc",
            }
        ],
        leie_rows,
    )
    assert len(matches) == 1
    assert matches[0].matched_by == ("name", "npi", "business")
    assert "Possible match" in matches[0].note


def test_nonmatching_input_returns_no_possible_matches() -> None:
    assert check_names(
        [{"first": "Other", "last": "Person", "npi": "", "business": ""}],
        [{"FIRSTNAME": "Ada", "LASTNAME": "Sample"}],
    ) == []


def test_cli_normalizes_staff_and_leie_headers(tmp_path: Path, monkeypatch, capsys) -> None:
    staff = tmp_path / "staff.csv"
    leie = tmp_path / "leie.csv"
    staff.write_text(
        "First Name,Last_Name,NPI,Business Name\n"
        "Ada,Sample,1234567890,Sample Dental LLC\n",
        encoding="utf-8",
    )
    leie.write_text(
        "FIRST NAME,LAST_NAME,BUS NAME,NPI,Excl Date\n"
        "Ada,Sample,Sample Dental LLC,1234567890,2020-01-01\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["oig_exclusion_check", str(staff), "--leie", str(leie)])

    assert main() == 0
    assert "possible name, npi, business match" in capsys.readouterr().out


def test_cli_reports_missing_staff_headers_with_exit_two(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    staff = tmp_path / "staff.csv"
    leie = Path(__file__).parent / "fixtures" / "leie.csv"
    staff.write_text("Employee,Department\nAda,Dental\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["oig_exclusion_check", str(staff), "--leie", str(leie)])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "staff CSV has no usable identifiers" in error
    assert "first and last" in error
    assert "business/business_name" in error
    assert "npi" in error


def test_cli_reports_missing_leie_headers_with_exit_two(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    staff = tmp_path / "staff.csv"
    leie = tmp_path / "leie.csv"
    staff.write_text("first,last\nAda,Sample\n", encoding="utf-8")
    leie.write_text("FIRSTNAME,LASTNAME\nAda,Sample\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["oig_exclusion_check", str(staff), "--leie", str(leie)])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "LEIE CSV is missing required header(s)" in error
    assert "BUSNAME" in error
    assert "NPI" in error
    assert "EXCLDATE" in error


@pytest.mark.parametrize(
    ("header", "value", "expected_match"),
    [
        ("Business Name", "Sample Dental LLC", "possible business match"),
        ("NPI", "1234567890", "possible npi match"),
    ],
)
def test_cli_screens_roster_with_business_or_npi_only(
    tmp_path: Path,
    monkeypatch,
    capsys,
    header: str,
    value: str,
    expected_match: str,
) -> None:
    staff = tmp_path / "staff.csv"
    leie = Path(__file__).parent / "fixtures" / "leie.csv"
    staff.write_text(f"{header}\n{value}\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["oig_exclusion_check", str(staff), "--leie", str(leie)])

    assert main() == 0
    assert expected_match in capsys.readouterr().out


def test_cli_rejects_roster_without_usable_identifiers(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    staff = tmp_path / "staff.csv"
    leie = Path(__file__).parent / "fixtures" / "leie.csv"
    staff.write_text("first,business_name,npi\nAda,,\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["oig_exclusion_check", str(staff), "--leie", str(leie)])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "no usable identifiers" in error
    assert "first and last" in error
    assert "business/business_name" in error
    assert "npi" in error


def test_download_target_cannot_resolve_to_staff_input(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    staff = tmp_path / "staff.csv"
    staff.write_text("first,last\nAda,Sample\n", encoding="utf-8")
    target = tmp_path / "subdir" / ".." / "staff.csv"
    monkeypatch.setattr(
        "sys.argv",
        ["oig_exclusion_check", str(staff), "--download", str(target)],
    )
    monkeypatch.setattr(
        "tools.oig_exclusion_check.download_leie",
        lambda *_args, **_kwargs: pytest.fail("download must not run for an input path"),
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "download target" in error
    assert "same path as input file" in error
    assert staff.read_text(encoding="utf-8") == "first,last\nAda,Sample\n"


def test_download_leie_replaces_target_after_success(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "UPDATED.csv"
    target.write_bytes(b"old contents")
    payload = b"LASTNAME,FIRSTNAME,MIDNAME,BUSNAME,NPI,EXCLTYPE,EXCLDATE,REINDATE\n"

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return payload

    monkeypatch.setattr("tools.oig_exclusion_check.urlopen", lambda *_args, **_kwargs: Response())

    assert download_leie(target) == len(payload)
    assert target.read_bytes() == payload
    assert list(tmp_path.glob(".UPDATED.csv.*.tmp")) == []


def test_download_leie_preserves_target_when_transfer_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "UPDATED.csv"
    target.write_bytes(b"old contents")

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            raise OSError("transfer interrupted")

    monkeypatch.setattr("tools.oig_exclusion_check.urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(OSError, match="transfer interrupted"):
        download_leie(target)

    assert target.read_bytes() == b"old contents"
    assert list(tmp_path.glob(".UPDATED.csv.*.tmp")) == []
