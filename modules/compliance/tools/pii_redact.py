from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


_PATTERNS = (
    (
        "chart",
        re.compile(
            r"\b(?:chart|mrn)\s*#?\s*[A-Z0-9-]*\d[A-Z0-9-]*\b",
            re.IGNORECASE,
        ),
        "[chart]",
    ),
    (
        "email",
        re.compile(
            r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9.-])",
            re.IGNORECASE,
        ),
        "[email]",
    ),
    (
        "ssn",
        re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
        "[ssn]",
    ),
    (
        "date",
        re.compile(
            r"(?<![\d/])(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/"
            r"(?:\d{2}|\d{4})(?!\d)"
        ),
        "[date]",
    ),
    (
        "date",
        re.compile(
            r"(?<!\d)\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)"
        ),
        "[date]",
    ),
    (
        "date",
        re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}\b",
            re.IGNORECASE,
        ),
        "[date]",
    ),
    (
        "phone",
        re.compile(
            r"(?<![\w$])(?:\+?1[ \t.-]?)?"
            r"(?:\(\d{3}\)[ \t.-]?|\d{3}[ \t.-])"
            r"\d{3}[ \t.-]\d{4}(?!\w)"
        ),
        "[phone]",
    ),
)
_NAME_WORD = r"(?:[A-Z]\.|[A-Z](?=[A-Za-z'’-]*[a-z])[A-Za-z'’-]+)"
_ROLE_NAME = re.compile(
    r"\b(?P<prefix>(?i:patient|hygienist|assistant|dentist|employee|dr\.|mrs\.|mr\.|ms\.|miss)"
    rf"[ \t]+)(?P<name>{_NAME_WORD}(?:[ \t]+{_NAME_WORD}){{0,2}})(?![A-Za-z])"
)


def redact(text: str) -> tuple[str, list[str]]:
    kinds: set[str] = set()
    for kind, pattern, placeholder in _PATTERNS:
        text, count = pattern.subn(placeholder, text)
        if count:
            kinds.add(kind)

    def replace_name(match: re.Match[str]) -> str:
        kinds.add("name")
        return f"{match.group('prefix')}[name]"

    text = _ROLE_NAME.sub(replace_name, text)
    return text, sorted(kinds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Redact personal information from text.")
    parser.add_argument("file", help="text file to redact, or - to read stdin")
    args = parser.parse_args()
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    redacted, kinds = redact(text)
    sys.stdout.write(redacted)
    print(f"PII kinds found: {', '.join(kinds) if kinds else 'none'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
