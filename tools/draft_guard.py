from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.mscd_lint import (
    NUMBER_WORDS,
    Finding,
    _parties,
    lint,
)


@dataclass(frozen=True)
class GuardResult:
    text: str
    fixed: list[str]
    flags: list[Finding]


_QUOTE_LINE = re.compile(r"^\s*>")
_CITED_QUOTE = re.compile(
    r'(?P<quote>"[^"\r\n]*"|“[^”\r\n]*”)\s*'
    r"\((?:T\.C\.A\.|Tenn\.|\d+\s+(?:CFR|C\.F\.R\.|U\.S\.C\.)|[^)]*§)[^)]*\)",
    re.IGNORECASE,
)
_NUMBER_WORD = rf"(?:{NUMBER_WORDS.replace(' ', '|')})"
_NUMBER_WORD_PHRASE_DOUBLET = re.compile(
    rf"\b{_NUMBER_WORD}(?:(?:\s+(?:and\s+)?|-){_NUMBER_WORD})*"
    r"\s+\(\s*\d+\s*\)",
    re.IGNORECASE,
)
_STANDARD_PARTIES = (
    "Business Associate",
    "Covered Entity",
    "Vendor",
    "Practice",
    "Company",
    "Provider",
    "Contractor",
    "Customer",
    "Client",
    "Dentist",
    "Associate",
    "Employer",
    "Employee",
    "Landlord",
    "Tenant",
    "Licensor",
    "Licensee",
    "Supplier",
    "Buyer",
    "Seller",
    "Consultant",
    "Owner",
)
_STANDARD_PARTY_PATTERN = "|".join(
    re.escape(party) for party in sorted(_STANDARD_PARTIES, key=len, reverse=True)
)
_THE_PARTY = re.compile(rf"\bThe\s+({_STANDARD_PARTY_PATTERN})\b")
_THE_PARTY_MODAL = re.compile(
    rf"\bThe\s+{_STANDARD_PARTY_PATTERN}\s+"
    r"(?P<verb>(?i:must|will))\b(?!\s+(?i:be)\b)"
)


def route(question: str) -> str | None:
    if not re.search(r"\b(?:draft|write|rewrite|revise|redline)\w*\b", question, re.I):
        return None
    if re.search(
        r"\b(?:contracts?|agreements?|clauses?|addenda?|BAAs?|NDAs?)\b",
        question,
        re.I,
    ):
        return "contract"
    if re.search(
        r"\b(?:one-way|polic(?:y|ies)|SOPs?|procedures?|checklists?)\b",
        question,
        re.I,
    ):
        return "one-way"
    return None


def _blockquote_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        if _QUOTE_LINE.match(line):
            ranges.append((offset, offset + len(line)))
        offset += len(line)
    return ranges


def _cited_quote_ranges(text: str) -> list[tuple[int, int]]:
    return [match.span("quote") for match in _CITED_QUOTE.finditer(text)]


def _backtick_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        if text[index] != "`":
            index += 1
            continue

        start = index
        while index < len(text) and text[index] == "`":
            index += 1
        delimiter_length = index - start
        search_from = index
        closing_end: int | None = None

        while search_from < len(text):
            closing = text.find("`", search_from)
            if closing < 0:
                break
            end = closing
            while end < len(text) and text[end] == "`":
                end += 1
            if end - closing == delimiter_length:
                closing_end = end
                break
            search_from = end

        if closing_end is None:
            index = start + delimiter_length
            continue
        ranges.append((start, closing_end))
        index = closing_end

    return ranges


def _overlaps(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start < range_end and range_start < end for range_start, range_end in ranges)


def _mask_ranges(text: str, ranges: list[tuple[int, int]]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end in sorted(ranges):
        if start < cursor:
            continue
        parts.append(text[cursor:start])
        parts.append("".join(char if char in "\r\n" else " " for char in text[start:end]))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _apply_edits(
    text: str, edits: list[tuple[int, int, str, str]]
) -> tuple[str, list[str]]:
    parts: list[str] = []
    fixed: list[str] = []
    cursor = 0
    for start, end, replacement, description in sorted(edits):
        if start < cursor:
            continue
        parts.extend((text[cursor:start], replacement))
        fixed.append(description)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), fixed


def _quote_excerpt(excerpt: str) -> str:
    return "'" + excerpt.replace("\\", "\\\\").replace("'", "\\'") + "'"


def guard(
    reply: str, mode: str, parties: list[str] | None = None
) -> GuardResult:
    if mode not in {"contract", "one-way"}:
        raise ValueError("mode must be 'contract' or 'one-way'")

    quote_ranges = _blockquote_ranges(reply)
    code_ranges = _backtick_ranges(reply)
    cited_quote_ranges = _cited_quote_ranges(reply)
    protected_ranges = sorted(quote_ranges + code_ranges + cited_quote_ranges)
    party_source = _mask_ranges(reply, protected_ranges)
    defined_parties = _parties(party_source, parties)
    inferred_parties = {match.group(1) for match in _THE_PARTY.finditer(party_source)}
    party_names = sorted(
        set(defined_parties) | inferred_parties,
        key=len,
        reverse=True,
    )

    edits: list[tuple[int, int, str, str]] = []
    for match in _NUMBER_WORD_PHRASE_DOUBLET.finditer(reply):
        if _overlaps(match.start(), match.end(), protected_ranges):
            continue
        digits = re.search(r"\(\s*(\d+)\s*\)$", match.group())
        if digits is None:
            continue
        replacement = digits.group(1)
        edits.append(
            (match.start(), match.end(), replacement, f"{match.group()} -> {replacement}")
        )

    if mode == "contract":
        modal_spans: set[tuple[int, int]] = set()
        for match in _THE_PARTY_MODAL.finditer(reply):
            if not _overlaps(match.start(), match.end(), protected_ranges):
                modal_spans.add(match.span("verb"))
        for party in party_names:
            pattern = re.compile(
                rf"\b{re.escape(party)}\s+"
                r"(?P<verb>(?i:must|will))\b(?!\s+(?i:be)\b)"
            )
            for match in pattern.finditer(reply):
                if not _overlaps(match.start(), match.end(), protected_ranges):
                    modal_spans.add(match.span("verb"))
        for start, end in sorted(modal_spans):
            edits.append((start, end, "shall", f"{reply[start:end]} -> shall"))

    fixed_text, fixed = _apply_edits(reply, edits)
    lint_text = _mask_ranges(fixed_text, _blockquote_ranges(fixed_text))
    lint_parties = _parties(lint_text, parties)
    lint_parties = sorted(
        set(lint_parties)
        | {match.group(1) for match in _THE_PARTY.finditer(lint_text)},
        key=len,
        reverse=True,
    )
    flags = [
        finding
        for finding in lint(lint_text, lint_parties, mode)
        if finding.rule in {"R-DIGITS", "R-MODAL", "R-ARCHAIC"}
    ]

    if fixed or flags:
        fixed_summary = ", ".join(fixed) if fixed else "none"
        flags_summary = (
            "; ".join(
                f"{finding.rule} line {finding.line} {_quote_excerpt(finding.excerpt)}"
                for finding in flags
            )
            if flags
            else "none"
        )
        footer = (
            "Drafting check (tools/draft_guard.py): "
            f"fixed {len(fixed)} item(s): {fixed_summary}; "
            f"{len(flags)} item(s) to review: {flags_summary}."
        )
        fixed_text += "\n\n" + footer

    return GuardResult(fixed_text, fixed, flags)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check and fix a contract or policy draft.")
    parser.add_argument("file", help="text file to guard, or - to read stdin")
    parser.add_argument("--mode", choices=("contract", "one-way"), required=True)
    parser.add_argument("--party", action="append", default=[])
    args = parser.parse_args()
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    sys.stdout.write(guard(text, args.mode, args.party).text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
