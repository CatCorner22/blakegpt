import csv
from pathlib import Path

import pytest

from tools.oig_exclusion_check import check_names, main


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
    assert "staff CSV is missing required header(s)" in error
    assert "first (accepted: first or first_name)" in error
    assert "last (accepted: last or last_name)" in error


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
