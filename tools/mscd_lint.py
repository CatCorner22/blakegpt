from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    line: int
    col: int
    rule: str
    excerpt: str
    message: str
    severity: str = "error"


NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
    "thirty forty fifty sixty seventy eighty ninety hundred thousand"
)
NUMBER_PATTERN = re.compile(rf"\b(?:{NUMBER_WORDS.replace(' ', '|')})\b", re.IGNORECASE)
NUMBER_DOUBLET_PATTERN = re.compile(
    rf"\b(?:{NUMBER_WORDS.replace(' ', '|')})\s+\(\s*\d+\s*\)", re.IGNORECASE
)
NUMBER_EXCEPTIONS = re.compile(
    r"\b(?:one\s+or\s+more|one\s+of|any\s+one|no\s+one|someone|anyone|everyone|"
    r"one\s+another|each\s+one)\b",
    re.IGNORECASE,
)


def _line_col(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    previous_newline = text.rfind("\n", 0, offset)
    return line, offset - previous_newline


def _excerpt(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return text[start:] if end < 0 else text[start:end]


def _parties(text: str, defined_parties: list[str] | None) -> list[str]:
    parties = set(defined_parties or [])
    pattern = re.compile(r'\(\s*(?:the\s+)?["“]([^"”]+)["”]\s*\)')
    parties.update(match.group(1) for match in pattern.finditer(text))
    return sorted((party for party in parties if party), key=len, reverse=True)


def lint(
    text: str,
    defined_parties: list[str] | None = None,
    mode: str = "contract",
) -> list[Finding]:
    if mode not in {"contract", "one-way"}:
        raise ValueError("mode must be 'contract' or 'one-way'")

    parties = _parties(text, defined_parties)
    findings: list[Finding] = []

    def add(rule: str, start: int, message: str, severity: str = "error") -> None:
        line, col = _line_col(text, start)
        findings.append(
            Finding(line, col, rule, _excerpt(text, start), message, severity)
        )

    exceptions = [match.span() for match in NUMBER_EXCEPTIONS.finditer(text)]
    number_offsets: set[int] = set()
    for pattern in (NUMBER_PATTERN, NUMBER_DOUBLET_PATTERN):
        for match in pattern.finditer(text):
            if any(start <= match.start() < end for start, end in exceptions):
                continue
            number_offsets.add(match.start())
    for offset in sorted(number_offsets):
        add("R-DIGITS", offset, "Use digits for numbers.")

    for match in re.finditer(r"(?:^|\n|[.!?]\s+)(\d)", text):
        add("R-LEADING-DIGIT", match.start(1), "A sentence must not start with a digit.")

    for party in parties:
        party_pattern = re.compile(
            rf"\b(?i:the|a|an)\s+({re.escape(party)})\b"
        )
        for match in party_pattern.finditer(text):
            add(
                "R-ARTICLE-PARTY",
                match.start(),
                "Do not place an article directly before a defined party name.",
            )

    xref_target = (
        r"(?:\d+(?:\.\d+)*(?:\([A-Za-z0-9]+\))*"
        r"|[IVXLCDM]+(?:\.[A-Z0-9]+)*(?:\([A-Za-z0-9]+\))*)"
    )
    xref_pattern = re.compile(
        rf"\b(?:sections?|paragraph|articles?|clauses?)\s+{xref_target}"
        rf"(?:\s*(?:,|and)\s*{xref_target})*",
        re.IGNORECASE,
    )
    for match in xref_pattern.finditer(text):
        add(
            "R-NUMERIC-XREF",
            match.start(),
            "Use a descriptive heading instead of a numeric cross-reference.",
        )

    labels = (
        (re.compile(r"^\s*([IVXLCDM]+)\.\s+"), 0),
        (re.compile(r"^\s*([A-Z])\.\s+"), 1),
        (re.compile(r"^\s*(\d+)\.\s+"), 2),
    )
    parenthesized_label = re.compile(r"^\s*\(([a-z]+)\)\s+", re.IGNORECASE)
    roman_labels = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
    malformed_labels = (
        re.compile(r"^\s*\d+\.\d+(?:\.\d+)*\s+"),
        re.compile(r"^\s*\([A-Z]\)\s+"),
        re.compile(r"^\s*[a-z]\.\s+"),
    )
    previous_tier: int | None = None
    absolute_start = 0
    for line_text in text.splitlines(keepends=True):
        malformed = next(
            (pattern.match(line_text) for pattern in malformed_labels if pattern.match(line_text)),
            None,
        )
        label_column = len(line_text) - len(line_text.lstrip())
        if malformed is not None:
            add("R-OUTLINE", absolute_start + label_column, "Use the required outline hierarchy.")
            absolute_start += len(line_text)
            continue
        label_match: re.Match[str] | None = None
        tier: int | None = None
        for pattern, candidate_tier in labels:
            label_match = pattern.match(line_text)
            if label_match:
                tier = candidate_tier
                break
        if tier is None:
            label_match = parenthesized_label.match(line_text)
            if label_match:
                label = label_match.group(1).casefold()
                if label in roman_labels:
                    tier = 4
                elif len(label) == 1:
                    tier = 3
                else:
                    add("R-OUTLINE", absolute_start + label_column, "Use the required outline hierarchy.")
                    absolute_start += len(line_text)
                    continue
        if tier is None:
            absolute_start += len(line_text)
            continue
        assert label_match is not None
        if previous_tier is not None and tier > previous_tier + 1:
            add("R-OUTLINE", absolute_start + label_column, "The outline skips a hierarchy level.")
        previous_tier = tier
        absolute_start += len(line_text)

    archaic_phrases = (
        "whereas",
        "witnesseth",
        "hereby",
        "herein",
        "hereof",
        "hereto",
        "thereof",
        "thereto",
        "therein",
        "aforesaid",
        "and/or",
        "for the avoidance of doubt",
        "including but not limited to",
        "null and void",
        "terms and conditions",
        "represents and warrants",
    )
    for phrase in archaic_phrases:
        for match in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE):
            add("R-ARCHAIC", match.start(), "Replace archaic or redundant wording.")
    for party in parties:
        for match in re.finditer(
            rf"\b(?:said|such)\s+{re.escape(party)}\b", text, re.IGNORECASE
        ):
            party_start = match.start()
            prefix = re.match(r"\s*(said|such)", text[party_start:], re.IGNORECASE)
            assert prefix is not None
            add("R-ARCHAIC", party_start, "Replace pointing words with the party name.")
    for match in re.finditer(r"\bsaid\s+the\b|\bsuch\s+the\b", text, re.IGNORECASE):
        add("R-ARCHAIC", match.start(), "Replace pointing words with a specific noun.")

    for match in re.finditer(
        r"\b(?:assignment|consideration|execut(?:e|ed|ion)|warrants?)\b",
        text,
        re.IGNORECASE,
    ):
        add(
            "R-TERM-OF-ART",
            match.start(),
            "Reserve this word for its legal meaning.",
            "review",
        )

    if mode == "one-way":
        modal_pattern = re.compile(
            r"\bshall\b|\bshould\b|\bis required to\b|\bis responsible for\b|"
            r"\bneeds to\b|\bcannot\b|\bmay not\b",
            re.IGNORECASE,
        )
        modal_message = "Use a direct obligation or prohibition; use 'must not' for a prohibition."
        for match in modal_pattern.finditer(text):
            add("R-MODAL", match.start(), modal_message)
    else:
        for expression in (
            "is required to",
            "agrees to",
            "undertakes to",
            "is obligated to",
            "shall be deemed",
        ):
            for match in re.finditer(rf"\b{re.escape(expression)}\b", text, re.IGNORECASE):
                add("R-MODAL", match.start(), "State the obligation directly.")
        for party in parties:
            for verb in ("will", "must"):
                for match in re.finditer(
                    rf"\b{re.escape(party)}\s+{verb}\b", text
                ):
                    add("R-MODAL", match.start(), "State the party's obligation directly.")

    return sorted(findings, key=lambda finding: (finding.line, finding.col, finding.rule))


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint a contract or policy draft.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--mode", choices=("contract", "one-way"), default="contract")
    parser.add_argument("--party", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = lint(args.file.read_text(encoding="utf-8"), args.party, args.mode)
    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    elif findings:
        for finding in findings:
            print(
                f"{finding.line}:{finding.col} {finding.rule} "
                f"[{finding.severity}]: {finding.message}: {finding.excerpt}"
            )
    else:
        print("No findings.")
    return int(any(finding.severity == "error" for finding in findings))


if __name__ == "__main__":
    raise SystemExit(main())
