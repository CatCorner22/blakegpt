#!/usr/bin/env python3
"""Fallback active-voice scanner for Chicken Little Overwatch.

The pattern set comes verbatim from the writing standard's fallback scan
(references/one-way-optimal-language.md, Verification). This wrapper adds a command
line, Markdown handling, paragraph joining (so a passive that wraps across a line
break still matches), and verbatim and mention markers. It flags more than it needs
to, on purpose. Decide each hit with Active Voice Step 2 (Decide). The eye check stays
mandatory: no scanner catches every reduced clause, heading fragment, or question.

Usage:   python3 av_scan.py [--strict] [--include-code] FILE [FILE ...]   ('-' reads standard input)
Exit:    0 no blocking hit; 1 one or more blocking hits; 2 a file could not be read.
Markers: <!-- av:verbatim --> ... <!-- /av:verbatim -->  text that a law requires word for word
         <!-- av:mention -->  ... <!-- /av:mention -->   deliberate "before" examples and cited titles
An unclosed marker zone counts as a blocking hit, because it would hide the rest of the file.
"""
import argparse
import re
import sys

P = (r"(?:\w{2,}ed|cut|put|set|read|hit|shut|hurt|spread|cast|shed|upset|run|overcome|done|given|taken|"
     r"mistaken|shaken|made|seen|written|known|shown|grown|thrown|blown|drawn|withdrawn|sworn|torn|worn|"
     r"born|found|told|held|withheld|kept|left|built|brought|bought|caught|taught|thought|sought|sent|"
     r"spent|meant|dealt|felt|led|misled|fed|bred|lit|met|paid|laid|said|sold|driven|hidden|broken|"
     r"chosen|frozen|spoken|stolen|forgotten|begun|struck|stuck|understood|beaten|bitten|eaten|forbidden|"
     r"ridden|proven|swollen|bound|lost|shot|heard|dug|hung|won)")
NOT = r"(?!(?:need|bed|red|seed|feed|speed|bleed|breed|proceed|exceed|succeed|hundred|sacred|naked|wicked)\b)"
ADV = r"(?:\s+(?:\w+ly|not|n't|also|only|then|often|usually|always|never|already|still|just|all|last|first|now|again|been|being|be))*"
DET = r"(?:the|a|an|your|my|his|her|its|our|their|this|that|these|those|each|every|any)"
PATTERNS = [
    ("be/get/stay + participle", rf"\b(?:am|is|are|was|were|be|been|being|'s|'re|isn't|aren't|wasn't|weren't|get|gets|got|gotten|getting|remains?|remained|stays?|stayed|seems?|seemed|looks?|looked|feels?|felt|appears?|appeared|becomes?|became){ADV}\s+{NOT}{P}\b"),
    ("question: be ... participle", rf"(?:^|[.?!]\s+)(?:(?:what|where|how|why|which|who|when)\s+)?(?:is|are|was|were|isn't|aren't|wasn't|weren't)\s+(?:\w+\s+){{1,4}}?{NOT}{P}\b[^.]*\?"),
    ("have/get/keep + object + participle", rf"\b(?:have|has|had|having|get|gets|got|keep|keeps|kept|leave|want|wants|need|needs|make|makes|find)\s+{DET}\s+(?:\w+\s+){{1,2}}?{NOT}{P}\b"),
    ("elliptical: if/when/as/once + participle", rf"\b(?:if|when|once|unless|until|as|while|although|though|where|than)(?:\s+(?:\w+ly|not|otherwise))*\s+{NOT}{P}\b"),
    ("sentence-initial participle", rf"(?:^|[.;:!?]\s+|,\s+)(?:not\s+(?:to\s+be\s+)?)?{NOT}{P}\b(?=\s*(?:,|\b(?:by|for|in|on|with|to|at|after|before|from|under|during)\b))"),
    ("need + -ing", r"\b(?:need|needs|needed|want|wants|require|requires)\s+(?!(?:nothing|something|anything|everything|bedding|clothing|counseling|training|nursing|screening)\b)\w{2,}ing\b"),
    ("noun + participle + by/prep", rf"\b(?!(?:i|you|we|he|she|it|they|who|which|that|the|a|an|to|and|or|have|has|had|be|is|are|was|were)\b)\w+\s+(?:not\s+)?{NOT}{P}\s+(?:by|in|on|at|after|before|for|from|with|during|under|into|through|late|early)\b"),
    ("thing + participle", rf"\b(?:anything|something|everything|nothing)\s+{NOT}{P}\b"),
    ("participle at end after object", rf"\b{DET}\s+\w+\s+{NOT}{P}\s*[.,;:)]"),
]
COMPILED = [(name, re.compile(p, re.I)) for name, p in PATTERNS]


def scan(text):
    """Return (pattern name, fragment, offset) for each hit in TEXT."""
    clean = text.replace("\u2019", "'").replace("*", " ").replace("`", " ")
    return [(name, " ".join(m.group(0).split()), m.start()) for name, rx in COMPILED for m in rx.finditer(clean)]


# --- Markdown reader (shared verbatim by av_scan.py and watchlist_scan.py; tests check that the copies match) ---
MARK = re.compile(r"<!--\s*(/?)av:(verbatim|mention)\s*-->")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
YAML_LINE = re.compile(r"^(?:\s*$|\s*#|[A-Za-z0-9_-]+\s*:|\s+\S|\s*-\s)")
BLOCK_START = re.compile(r"^\s*(?:#{1,6}\s|\||[-*+]\s|\d+[.)]\s|>)")
SINGLE_LINE = re.compile(r"^\s*(?:#{1,6}\s|\|)")


class InputError(Exception):
    """A file that the scanner cannot read as UTF-8 text."""


def read_lines(path):
    """Return the lines of PATH ('-' means standard input) without line endings."""
    if path == "-":
        return sys.stdin.read().lstrip("\ufeff").splitlines()
    try:
        with open(path, encoding="utf-8-sig") as handle:
            return handle.read().splitlines()
    except FileNotFoundError:
        raise InputError(f"{path}: no such file")
    except IsADirectoryError:
        raise InputError(f"{path}: is a folder; pass the files inside it")
    except UnicodeDecodeError as error:
        raise InputError(f"{path}: not UTF-8 text (byte {error.start}); convert it to UTF-8 first")
    except OSError as error:
        raise InputError(f"{path}: {error.strerror}")


def front_matter_end(lines):
    """Return the index of the closing front-matter line, or -1 if the file has no front matter."""
    if not lines or lines[0].strip() != "---":
        return -1
    for index in range(1, len(lines)):
        if lines[index].strip() in ("---", "..."):
            return index
        if not YAML_LINE.match(lines[index]):
            return -1
    return -1


def fence_lines(lines, start):
    """Return the set of line indexes inside closed code fences, and the index of each unclosed opener."""
    inside, unclosed, index = set(), [], start
    while index < len(lines):
        opener = FENCE.match(lines[index])
        if not opener:
            index += 1
            continue
        mark = opener.group(1)
        close = next((j for j in range(index + 1, len(lines))
                      if re.match(rf"^\s{{0,3}}{re.escape(mark[0])}{{{len(mark)},}}\s*$", lines[j])), None)
        if close is None:
            unclosed.append(index)
            index += 1
            continue
        inside.update(range(index, close + 1))
        index = close + 1
    return inside, unclosed


def paragraphs(lines, include_code=False):
    """Yield (zone, first_line_number, text) for each paragraph, and collect warnings.

    Zone is TEXT, VERBATIM, or MENTION. A paragraph joins wrapped lines with a newline,
    so a pattern can match across a line break.
    """
    warnings = []
    end = front_matter_end(lines)
    if lines and lines[0].strip() == "---" and end == -1:
        warnings.append("line 1: '---' opens no valid front matter; the scanner reads the file as text")
    start = end + 1
    fenced, unclosed = (set(), []) if include_code else fence_lines(lines, start)
    for index in unclosed:
        warnings.append(f"line {index + 1}: code fence never closes; the scanner reads the rest as text")
    out, zone, buffer, first = [], "TEXT", [], 0

    def flush():
        if buffer:
            out.append((zone, first, "\n".join(buffer)))
        buffer.clear()

    for index in range(start, len(lines)):
        line = lines[index]
        marker = MARK.search(line)
        if marker:
            flush()
            closing, kind = marker.group(1), marker.group(2).upper()
            if closing and zone != kind:
                warnings.append(f"line {index + 1}: closing av:{kind.lower()} marker has no matching opener")
            if not closing and zone != "TEXT":
                warnings.append(f"line {index + 1}: av:{kind.lower()} opens inside an open av:{zone.lower()} zone")
            zone = "TEXT" if closing else kind
            continue
        if index in fenced or not line.strip() or line.lstrip().startswith("<!--") or re.match(r"^\s*\|?\s*:?-{3,}", line):
            flush()
            continue
        if BLOCK_START.match(line):
            flush()
        if not buffer:
            first = index + 1
        buffer.append(line)
        if SINGLE_LINE.match(line):
            flush()
    flush()
    if zone != "TEXT":
        warnings.append(f"end of file: av:{zone.lower()} zone never closes")
    return out, warnings, zone != "TEXT"


def line_of(first, text, offset):
    return first + text.count("\n", 0, offset)
# --- end Markdown reader ---


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("files", nargs="+", help="Markdown or text files; '-' reads standard input")
    parser.add_argument("--strict", action="store_true", help="count hits inside av:mention zones as blocking")
    parser.add_argument("--include-code", action="store_true", help="also scan fenced code blocks")
    args = parser.parse_args(argv)
    blocking = verbatim = mention = failed = 0
    for path in args.files:
        try:
            lines = read_lines(path)
        except InputError as error:
            print(f"ERROR {error}", file=sys.stderr)
            failed += 1
            continue
        found, warnings, open_zone = paragraphs(lines, args.include_code)
        for warning in warnings:
            print(f"{path}: WARNING {warning}", file=sys.stderr)
        if open_zone:
            blocking += 1
        seen = set()
        for zone, first, text in found:
            for name, fragment, offset in scan(text):
                number = line_of(first, text, offset)
                if (number, name, fragment) in seen:
                    continue
                seen.add((number, name, fragment))
                label = {"TEXT": "HIT", "VERBATIM": "VERBATIM", "MENTION": "MENTION"}[zone]
                print(f"{path}:{number}: [{label}:{name}] {fragment}")
                if zone == "TEXT" or (zone == "MENTION" and args.strict):
                    blocking += 1
                elif zone == "VERBATIM":
                    verbatim += 1
                else:
                    mention += 1
    print(f"blocking={blocking} verbatim={verbatim} mention={mention} unreadable={failed}", file=sys.stderr)
    if failed:
        return 2
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
