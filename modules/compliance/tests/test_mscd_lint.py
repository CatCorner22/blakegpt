from tools.mscd_lint import _classify_outline_label, lint


def rules(text: str, *, parties: list[str] | None = None, mode: str = "contract") -> set[str]:
    return {finding.rule for finding in lint(text, parties, mode)}


def test_clean_contract_paragraph_has_no_findings() -> None:
    text = (
        'Company shall pay Provider $2,500.00 within 30 days after Provider delivers '
        'each invoice, as set forth in the paragraph titled "Compensation".'
    )
    assert lint(text, ["Company", "Provider"]) == []


def test_digits_rule_and_exceptions() -> None:
    assert "R-DIGITS" in rules("The office pays thirty dollars.")
    assert "R-DIGITS" not in rules(
        "One or more records, one of the files, any one, no one, someone, anyone, "
        "everyone, one another, and each one."
    )
    assert "R-DIGITS" in rules("Thirty (30) days.")


def test_leading_digit_rule() -> None:
    assert "R-LEADING-DIGIT" in rules("30 days apply.")
    assert "R-LEADING-DIGIT" not in rules("The 30-day period applies.")
    assert "R-LEADING-DIGIT" not in rules("1. Numbered item.")
    assert "R-LEADING-DIGIT" not in rules("(a) Lettered item.")
    assert "R-LEADING-DIGIT" in rules("1. 30 days apply.")
    assert "R-LEADING-DIGIT" in rules("(a) 30 days apply.")
    findings = [
        finding
        for finding in lint("A. 30 days apply.")
        if finding.rule == "R-LEADING-DIGIT"
    ]
    assert len(findings) == 1


def test_article_party_rule_and_definition_detection() -> None:
    assert "R-ARTICLE-PARTY" in rules('The Company gives notice. (the "Company")')
    assert "R-ARTICLE-PARTY" not in rules("Company gives notice.", parties=["Company"])


def test_numeric_cross_reference_rule() -> None:
    assert "R-NUMERIC-XREF" in rules("See Section 3.2 and paragraph 2(b).")
    assert "R-NUMERIC-XREF" in rules("Sections 4 and 5 apply.")
    assert "R-NUMERIC-XREF" in rules("Article IV and clause 7 apply.")
    assert "R-NUMERIC-XREF" in rules("Section IV. applies.")
    assert "R-NUMERIC-XREF" not in rules('See the section titled "Payment".')
    assert "R-NUMERIC-XREF" not in rules("This paragraph describes payment.")
    assert "R-NUMERIC-XREF" not in rules("Section IVetera describes payment.")


def test_numeric_cross_reference_accepts_lettered_and_subpart_targets() -> None:
    assert "R-NUMERIC-XREF" in rules("See Section 2A for payment.")
    assert "R-NUMERIC-XREF" in rules("See Section 3.1(b) for payment.")
    assert "R-NUMERIC-XREF" in rules("See Article IV(a) for payment.")


def test_outline_hierarchy_and_invalid_labels() -> None:
    clean = "I. First\nA. Second\n1. Third\n(a) Fourth\n(i) Fifth"
    assert "R-OUTLINE" not in rules(clean)
    assert "R-OUTLINE" in rules("I. First\n1. Skips a level")
    assert "R-OUTLINE" in rules("A. Parent\n(ii) Skips a level")
    assert "R-OUTLINE" in rules("(A) Invalid uppercase label\na. Invalid lowercase label\n1.1 Invalid decimal")


def test_ambiguous_outline_labels_use_sequence_context() -> None:
    assert "R-OUTLINE" not in rules("I. First\nII. Second")
    assert "R-OUTLINE" not in rules("B. First\nC. Second")
    assert "R-OUTLINE" not in rules("A. Parent\n1. Child\n(a) Subitem\n(i) Sub-subitem")
    assert "R-OUTLINE" not in rules("(h) Letter h\n(i) Letter i")
    assert "R-OUTLINE" in rules("A. Parent\n(ii) Skips levels")
    assert _classify_outline_label([(1, "I"), (2, "I")], None, {}) == 1
    assert _classify_outline_label([(1, "II")], 1, {1: "I"}) == 1
    assert _classify_outline_label([(1, "C"), (2, "C")], 2, {2: "B"}) == 2
    assert _classify_outline_label([(1, "D"), (2, "D")], 2, {2: "C"}) == 2
    assert _classify_outline_label([(1, "V"), (2, "V")], 1, {1: "IV"}) == 1
    assert _classify_outline_label([(1, "X"), (2, "X")], 1, {1: "IX"}) == 1
    assert _classify_outline_label([(1, "L"), (2, "L")], 1, {1: "XLIX"}) == 1
    assert _classify_outline_label([(1, "M"), (2, "M")], 1, {1: "CMXCIX"}) == 1
    assert _classify_outline_label([(4, "i"), (5, "i")], 4, {4: "a"}) == 5
    assert _classify_outline_label([(4, "i"), (5, "i")], 4, {4: "h"}) == 4
    assert _classify_outline_label([(4, "v"), (5, "v")], 4, {4: "u"}) == 4
    assert _classify_outline_label([(4, "x"), (5, "x")], 5, {5: "ix"}) == 5


def test_archaic_rule_and_such_as_exception() -> None:
    assert "R-ARCHAIC" in rules("Whereas, said Company acts hereby.")
    assert "R-ARCHAIC" in rules('Such Company acts. ("Company")')
    assert "R-ARCHAIC" in rules("Such the record.")
    assert "R-ARCHAIC" not in rules("Such as the listed example.")


def test_term_of_art_is_review_severity() -> None:
    findings = lint("The consideration is assignment of rights.")
    terms = [finding for finding in findings if finding.rule == "R-TERM-OF-ART"]
    assert len(terms) == 2
    assert all(finding.severity == "review" for finding in terms)
    assert "R-TERM-OF-ART" not in rules("The office transfers files.")


def test_contract_modal_rule() -> None:
    assert "R-MODAL" in rules("Company will pay and Provider must deliver.", parties=["Company", "Provider"])
    assert "R-MODAL" in rules("The provider is required to respond.")
    assert "R-MODAL" not in rules("A manager will review the request.")


def test_one_way_modal_rule() -> None:
    assert "R-MODAL" in rules(
        "A manager should act, cannot delay, may not defer, and shall document.",
        mode="one-way",
    )
    assert "R-MODAL" not in rules("A manager must not disclose information.", mode="one-way")
