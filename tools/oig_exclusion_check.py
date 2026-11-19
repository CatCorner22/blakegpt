from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.request import Request, urlopen


LEIE_URL = "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv"
VERIFY_URL = "https://exclusions.oig.hhs.gov"
STAFF_HEADERS = {
    "first": ("first", "first_name"),
    "last": ("last", "last_name"),
    "npi": ("npi",),
    "business": ("business", "business_name"),
}
LEIE_HEADERS = {
    "FIRSTNAME": ("FIRSTNAME",),
    "LASTNAME": ("LASTNAME",),
    "BUSNAME": ("BUSNAME",),
    "NPI": ("NPI",),
    "EXCLDATE": ("EXCLDATE",),
}


@dataclass(frozen=True)
class PossibleMatch:
    input_row: int
    matched_by: tuple[str, ...]
    first_name: str
    last_name: str
    business_name: str
    npi: str
    exclusion_date: str
    note: str = f"Possible match; verify at {VERIFY_URL}."


def download_leie(path: Path, timeout: int = 45) -> int:
    request = Request(LEIE_URL, headers={"User-Agent": "office-compliance-assistant/1.0"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise OSError(f"LEIE download returned HTTP {response.status}")
        data = response.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(data)


def check_names(
    input_rows: list[dict[str, str]],
    leie_rows: list[dict[str, str]],
) -> list[PossibleMatch]:
    matches: list[PossibleMatch] = []
    for input_index, person in enumerate(input_rows, 1):
        first = str(person.get("first") or "").strip()
        last = str(person.get("last") or "").strip()
        npi = str(person.get("npi") or "").strip()
        business = str(person.get("business") or "").strip()
        for excluded in leie_rows:
            excluded_first = str(excluded.get("FIRSTNAME") or "").strip()
            excluded_last = str(excluded.get("LASTNAME") or "").strip()
            excluded_business = str(excluded.get("BUSNAME") or "").strip()
            excluded_npi = str(excluded.get("NPI") or "").strip()
            reasons: list[str] = []
            if first and last and (
                first.casefold() == excluded_first.casefold()
                and last.casefold() == excluded_last.casefold()
            ):
                reasons.append("name")
            if npi and excluded_npi and npi == excluded_npi:
                reasons.append("npi")
            if business and excluded_business and business.casefold() == excluded_business.casefold():
                reasons.append("business")
            if reasons:
                matches.append(
                    PossibleMatch(
                        input_index,
                        tuple(reasons),
                        excluded_first,
                        excluded_last,
                        excluded_business,
                        excluded_npi,
                        str(excluded.get("EXCLDATE") or "").strip(),
                    )
                )
    return matches


def _normalize_header(header: str) -> str:
    return header.casefold().replace(" ", "").replace("_", "")


def _read_csv(
    path: Path,
    aliases: dict[str, tuple[str, ...]],
    required: tuple[str, ...],
    source_name: str,
) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        headers = reader.fieldnames or []
        original_by_normalized: dict[str, str] = {}
        for header in headers:
            original_by_normalized.setdefault(_normalize_header(header), header)
        selected: dict[str, str | None] = {}
        missing: list[str] = []
        for canonical, accepted in aliases.items():
            original = next(
                (
                    original_by_normalized[_normalize_header(alias)]
                    for alias in accepted
                    if _normalize_header(alias) in original_by_normalized
                ),
                None,
            )
            selected[canonical] = original
            if canonical in required and original is None:
                missing.append(f"{canonical} (accepted: {' or '.join(accepted)})")
        if missing:
            raise ValueError(
                f"{source_name} CSV is missing required header(s): "
                f"{', '.join(missing)}. Expected headers: "
                f"{', '.join(', '.join(aliases[field]) for field in required)}."
            )
        return [
            {
                canonical: (row.get(original, "") or "") if original else ""
                for canonical, original in selected.items()
            }
            for row in reader
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check names against a local HHS-OIG LEIE copy.")
    parser.add_argument("input", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--leie", type=Path)
    source.add_argument("--download", type=Path, metavar="PATH")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        staff_rows = _read_csv(
            args.input,
            STAFF_HEADERS,
            ("first", "last"),
            "staff",
        )
        leie_path = args.leie
        if args.download:
            size = download_leie(args.download)
            print(f"Downloaded {size} bytes to {args.download}.", file=sys.stderr)
            leie_path = args.download
        assert leie_path is not None
        leie_rows = _read_csv(
            leie_path,
            LEIE_HEADERS,
            ("FIRSTNAME", "LASTNAME", "BUSNAME", "NPI", "EXCLDATE"),
            "LEIE",
        )
    except ValueError as exc:
        parser.error(str(exc))
    matches = check_names(staff_rows, leie_rows)
    if args.json:
        print(json.dumps([asdict(item) for item in matches], indent=2))
    elif matches:
        for item in matches:
            print(
                f"Input row {item.input_row}: possible {', '.join(item.matched_by)} match "
                f"for {item.first_name} {item.last_name} / {item.business_name} "
                f"(NPI {item.npi}; exclusion date {item.exclusion_date}). {item.note}"
            )
    else:
        print(f"No possible matches. Verify against {VERIFY_URL}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
