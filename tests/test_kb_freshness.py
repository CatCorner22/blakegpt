from datetime import date
from pathlib import Path

from tools.kb_freshness import (
    Card,
    assess_card,
    build_query,
    check_federal_register,
    discover_cards,
    load_card,
    parse_front_matter,
)


def test_front_matter_parses_scalars_and_lists() -> None:
    metadata = parse_front_matter(
        "---\nid: card\nsources:\n  - https://example.com/a\ncfr: [29 CFR 1910.1030]\n---\ntext"
    )
    assert metadata["id"] == "card"
    assert metadata["sources"] == ["https://example.com/a"]
    assert metadata["cfr"] == ["29 CFR 1910.1030"]


def test_card_freshness_unverified_and_missing_sources() -> None:
    fixture = load_card(Path(__file__).parent / "fixtures/knowledge/unverified.md")
    codes = {finding.code for finding in assess_card(fixture, date(2026, 7, 1))}
    assert codes == {"UNVERIFIED", "NO-SOURCES"}


def test_stale_card_finding() -> None:
    card = Card("card.md", "stale", "Stale", "federal", "verified", date(2025, 1, 1), 90)
    assert [finding.code for finding in assess_card(card, date(2025, 4, 2))] == ["STALE", "NO-SOURCES"]


def test_build_query_uses_documented_parameter_names() -> None:
    params = build_query("29 CFR 1910.1030", date(2026, 1, 2))
    assert ("conditions[cfr][title]", "29") in params
    assert ("conditions[cfr][part]", "1910") in params
    assert ("conditions[publication_date][gte]", "2026-01-02") in params
    assert ("per_page", "20") in params
    assert [value for key, value in params if key == "fields[]"] == [
        "title",
        "html_url",
        "publication_date",
        "type",
    ]


def test_federal_register_query_is_sent_once_per_citation(monkeypatch) -> None:
    card = Card(
        "card.md",
        "sample",
        "Sample",
        "federal",
        "verified",
        date(2026, 1, 1),
        cfr=("29 CFR 1910.1030",),
    )
    calls = []

    def fake_fetch(params):
        calls.append(params)
        return {
            "results": [
                {
                    "title": "Sample update",
                    "html_url": "https://example.com/update",
                    "publication_date": "2026-02-01",
                    "type": "Rule",
                }
            ]
        }

    monkeypatch.setattr("tools.kb_freshness.fetch_documents", fake_fetch)
    documents = check_federal_register(card)
    assert len(calls) == 1
    assert documents[0].title == "Sample update"
    assert documents[0].document_type == "Rule"


def test_discover_cards_loads_only_markdown_cards() -> None:
    fixture_dir = Path(__file__).parent / "fixtures/knowledge"
    cards = discover_cards(fixture_dir)
    assert {card.id for card in cards} == {"sample-fresh", "sample-unverified"}
