from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
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
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
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


def _validate_download_target(target: Path, input_paths: list[Path]) -> None:
    resolved_target = target.resolve()
    for input_path in input_paths:
        if resolved_target == input_path.resolve():
            raise ValueError(
                f"download target {target} resolves to the same path as "
                f"input file {input_path}"
            )


def _validate_staff_identifiers(rows: list[dict[str, str]]) -> None:
    if any(
        (row["first"].strip() and row["last"].strip())
        or row["business"].strip()
        or row["npi"].strip()
        for row in rows
    ):
        return
    raise ValueError(
        "staff CSV has no usable identifiers. Accepted headers are first and last "
        "(first/first_name and last/last_name), business/business_name, or npi."
    )


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
        duplicate_headers: list[tuple[str, str]] = []
        for header in headers:
            normalized = _normalize_header(header)
            original = original_by_normalized.get(normalized)
            if original is None:
                original_by_normalized[normalized] = header
            else:
                duplicate_headers.append((original, header))
        if duplicate_headers:
            details = "; ".join(
                f"{first!r} and {second!r}" for first, second in duplicate_headers
            )
            raise ValueError(
                f"{source_name} CSV has duplicate headers after normalization: {details}"
            )
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
        if args.download:
            input_paths = [args.input]
            if args.leie is not None:
                input_paths.append(args.leie)
            _validate_download_target(args.download, input_paths)
        staff_rows = _read_csv(
            args.input,
            STAFF_HEADERS,
            (),
            "staff",
        )
        _validate_staff_identifiers(staff_rows)
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
