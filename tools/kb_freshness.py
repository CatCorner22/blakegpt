from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FEDERAL_REGISTER_URL = "https://www.federalregister.gov/api/v1/documents.json"
CFR_PATTERN = re.compile(r"^\s*(\d+)\s+CFR\s+(\d+)")


@dataclass(frozen=True)
class Card:
    path: str
    id: str
    title: str
    jurisdiction: str
    status: str
    last_verified: date
    review_days: int = 90
    sources: tuple[str, ...] = ()
    cfr: tuple[str, ...] = ()


@dataclass(frozen=True)
class CardFinding:
    card_id: str
    code: str
    message: str


@dataclass(frozen=True)
class FederalRegisterDocument:
    citation: str
    title: str
    html_url: str
    publication_date: str
    document_type: str


@dataclass
class CardReport:
    card: Card
    findings: list[CardFinding] = field(default_factory=list)
    federal_register_documents: list[FederalRegisterDocument] = field(default_factory=list)


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def parse_front_matter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("knowledge card must start with a --- front-matter line")
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ValueError("knowledge card has no closing --- front-matter line") from exc
    metadata: dict[str, Any] = {}
    current_list: str | None = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- ") and current_list:
            metadata[current_list].append(_scalar(line.lstrip()[2:]))
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not value:
            metadata[key] = []
            current_list = key
        elif value.startswith("[") and value.endswith("]"):
            content = value[1:-1].strip()
            metadata[key] = [_scalar(part) for part in content.split(",") if part.strip()]
            current_list = None
        else:
            metadata[key] = _scalar(value)
            current_list = None
    return metadata


def load_card(path: Path) -> Card:
    metadata = parse_front_matter(path.read_text(encoding="utf-8"))
    required = ("id", "title", "jurisdiction", "status", "last_verified")
    missing = [key for key in required if not metadata.get(key)]
    if missing:
        raise ValueError(f"{path} is missing required fields: {', '.join(missing)}")
    try:
        verified = date.fromisoformat(str(metadata["last_verified"]))
        review_days = int(metadata.get("review_days", 90))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{path} has an invalid date or review_days value") from exc
    if review_days < 0:
        raise ValueError("review_days must not be negative")
    sources = metadata.get("sources", [])
    citations = metadata.get("cfr", [])
    if isinstance(sources, str):
        sources = [sources]
    if isinstance(citations, str):
        citations = [citations]
    return Card(
        str(path),
        str(metadata["id"]),
        str(metadata["title"]),
        str(metadata["jurisdiction"]),
        str(metadata["status"]),
        verified,
        review_days,
        tuple(str(source) for source in sources),
        tuple(str(citation) for citation in citations),
    )


def assess_card(card: Card, today: date | None = None) -> list[CardFinding]:
    current_date = today or date.today()
    findings: list[CardFinding] = []
    if (current_date - card.last_verified).days > card.review_days:
        findings.append(
            CardFinding(
                card.id,
                "STALE",
                f"Last verified {card.last_verified.isoformat()}, beyond the {card.review_days}-day review interval.",
            )
        )
    if card.status == "unverified":
        findings.append(CardFinding(card.id, "UNVERIFIED", "Card status is unverified."))
    if not card.sources:
        findings.append(CardFinding(card.id, "NO-SOURCES", "Card has no source URLs."))
    return findings


def build_query(citation: str, last_verified: date) -> list[tuple[str, str]]:
    match = CFR_PATTERN.match(citation)
    if not match:
        raise ValueError(f"unsupported CFR citation: {citation}")
    title, part = match.groups()
    params = [
        ("conditions[cfr][title]", title),
        ("conditions[cfr][part]", part),
        ("conditions[publication_date][gte]", last_verified.isoformat()),
        ("per_page", "20"),
        ("fields[]", "title"),
        ("fields[]", "html_url"),
        ("fields[]", "publication_date"),
        ("fields[]", "type"),
    ]
    return params


def fetch_documents(params: list[tuple[str, str]], timeout: int = 30) -> dict[str, Any]:
    url = f"{FEDERAL_REGISTER_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "office-compliance-assistant/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_federal_register(card: Card) -> list[FederalRegisterDocument]:
    documents: list[FederalRegisterDocument] = []
    for citation in card.cfr:
        result = fetch_documents(build_query(citation, card.last_verified))
        for item in result.get("results", []):
            documents.append(
                FederalRegisterDocument(
                    citation,
                    str(item.get("title", "")),
                    str(item.get("html_url", "")),
                    str(item.get("publication_date", "")),
                    str(item.get("type", "")),
                )
            )
    return documents


def discover_cards(directory: Path) -> list[Card]:
    return [load_card(path) for path in sorted(directory.glob("**/*.md"))]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check knowledge-card freshness.")
    parser.add_argument("directory", nargs="?", type=Path, default=Path("knowledge"))
    parser.add_argument("--federal-register", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    reports = [
        CardReport(
            card,
            assess_card(card),
            check_federal_register(card) if args.federal_register else [],
        )
        for card in discover_cards(args.directory)
    ]
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "card": {
                            **asdict(report.card),
                            "last_verified": report.card.last_verified.isoformat(),
                        },
                        "findings": [asdict(item) for item in report.findings],
                        "federal_register_documents": [
                            asdict(item) for item in report.federal_register_documents
                        ],
                    }
                    for report in reports
                ],
                indent=2,
            )
        )
    elif not reports:
        print("No knowledge cards found.")
    else:
        for report in reports:
            for finding in report.findings:
                print(f"{report.card.id} {finding.code}: {finding.message}")
            for document in report.federal_register_documents:
                print(
                    f"{report.card.id} {document.publication_date} "
                    f"{document.document_type}: {document.title} {document.html_url}"
                )
        if not any(report.findings or report.federal_register_documents for report in reports):
            print("No findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
