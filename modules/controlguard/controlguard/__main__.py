import argparse
import os
from pathlib import Path
import sqlite3
import sys

from .app import ENGINES, run_engine
from .inputs import decode, encode
from .ledger import Ledger


def main() -> int:
    parser = argparse.ArgumentParser(prog="controlguard")
    parser.add_argument("--ledger", type=Path,
                        default=Path(os.environ.get("CONTROLGUARD_LEDGER", "controlguard.sqlite3")))
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run a tool with a JSON object.")
    run.add_argument("engine", choices=ENGINES)
    run.add_argument("input", nargs="?", default="-", help="JSON file, or - for stdin.")
    web = commands.add_parser("web", help="Start the local site.")
    web.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    ledger = Ledger(args.ledger)
    try:
        if args.command == "web":
            from .web import serve
            serve(args.port, ledger)
        else:
            raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
            print(encode(run_engine(args.engine, decode(raw), ledger), pretty=True))
    except (OSError, ValueError, RecursionError, sqlite3.Error) as error:
        print(encode({"error": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
