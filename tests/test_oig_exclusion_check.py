import csv
from pathlib import Path

from tools.oig_exclusion_check import check_names


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
