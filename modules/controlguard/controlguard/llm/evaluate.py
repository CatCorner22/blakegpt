import argparse
from pathlib import Path
import re

from controlguard.inputs import Fields, decode, encode, fields

from .tools import SCHEMAS, validate

TOOL_CALL = re.compile(r"\s*<tool_call>\s*(.*?)\s*</tool_call>\s*(?:<\|im_end\|>)?\s*", re.S)


def load_rows(path: Path) -> list[Fields]:
    return [decode(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def measure(expected_rows: list[Fields], predictions: list[str]) -> Fields:
    if len(expected_rows) != len(predictions) or not predictions:
        raise ValueError("Provide one prediction per nonempty evaluation row.")
    valid = names = correct = 0
    for row, prediction in zip(expected_rows, predictions, strict=True):
        target = fields(row["expected"])
        match = TOOL_CALL.fullmatch(prediction)
        try:
            answer = decode(match[1] if match is not None else prediction)
        except ValueError:
            continue
        valid += 1
        name = answer.get("name")
        if not isinstance(name, str) or name != target["name"] or name not in SCHEMAS:
            continue
        names += 1
        try:
            validate(answer.get("arguments"), SCHEMAS[name])
        except ValueError:
            continue
        correct += int(set(answer) == {"name", "arguments"} and answer["arguments"] == target["arguments"])
    total = len(predictions)
    return {"examples": total, "valid_json": valid, "correct_tool": names, "exact_tool_call": correct}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score held-out tool-call predictions.")
    parser.add_argument("expected", type=Path)
    parser.add_argument("predictions", type=Path, help="JSONL with a prediction string per row.")
    parser.add_argument("--limit", type=int, help="Use the first N expected rows.")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("Use a positive limit.")
    rows = load_rows(args.predictions)
    predictions = [str(row["prediction"]) for row in rows]
    print(encode(measure(load_rows(args.expected)[:args.limit], predictions), pretty=True))


if __name__ == "__main__":
    main()
