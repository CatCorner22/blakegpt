from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import sqlite3

from .inputs import Fields, encode

LAPSE = timedelta(hours=336)
GENESIS = "0" * 64
SCHEMA = """
CREATE TABLE IF NOT EXISTS attestations (
    seq INTEGER PRIMARY KEY, subject TEXT NOT NULL, control TEXT NOT NULL,
    signer TEXT NOT NULL, actor TEXT NOT NULL, cadence TEXT NOT NULL, artifact TEXT NOT NULL,
    signed_at TEXT NOT NULL, prior_hash TEXT NOT NULL, hash TEXT NOT NULL
)
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute(SCHEMA)
        return connection

    @staticmethod
    def _digest(entry: Fields) -> str:
        return sha256(encode(entry).encode("utf-8")).hexdigest()

    @staticmethod
    def _timestamp(value: datetime) -> str:
        if value.utcoffset() is None:
            raise ValueError("Ledger timestamps need a timezone.")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")

    def _read(self, connection: sqlite3.Connection) -> list[Fields]:
        prior = GENESIS
        last_time: str | None = None
        records: list[Fields] = []
        for row in connection.execute("SELECT * FROM attestations ORDER BY seq"):
            entry: Fields = dict(row)
            digest = entry.pop("hash")
            signed_at = str(entry["signed_at"])
            if (entry["seq"] != len(records) + 1
                    or any(not isinstance(value, str) for key, value in entry.items() if key != "seq")
                    or entry["prior_hash"] != prior
                    or digest != self._digest(entry) or (last_time is not None and signed_at < last_time)):
                raise ValueError("Ledger verification failed. No risk reduction applies.")
            prior = str(digest)
            last_time = signed_at
            records.append({**entry, "hash": digest})
        return records

    def verify(self) -> list[Fields]:
        if not self.path.exists():
            return []
        with closing(self._connect()) as connection:
            return self._read(connection)

    def append(
        self, *, subject: str, control: str, signer: str, actor: str,
        cadence: str, artifact: str, now: datetime | None = None,
    ) -> Fields:
        if not all(value.strip() for value in (subject, control, signer, actor, cadence, artifact)):
            raise ValueError("Attestations require a subject, control, signer, actor, cadence and artifact.")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            records = self._read(connection)
            signed_at = self._timestamp(now if now is not None else utc_now())
            if records and signed_at < str(records[-1]["signed_at"]):
                raise ValueError("A new sign-off cannot predate the ledger head.")
            entry: Fields = {
                "seq": len(records) + 1, "subject": subject, "control": control, "signer": signer,
                "actor": actor, "cadence": cadence, "artifact": artifact, "signed_at": signed_at,
                "prior_hash": records[-1]["hash"] if records else GENESIS,
            }
            entry["hash"] = self._digest(entry)
            connection.execute(
                "INSERT INTO attestations VALUES "
                "(:seq, :subject, :control, :signer, :actor, :cadence, :artifact, :signed_at, :prior_hash, :hash)",
                entry,
            )
            return entry

    def status(self, subject: str, control: str, now: datetime | None = None) -> tuple[str, str | None]:
        current = datetime.fromisoformat(self._timestamp(now if now is not None else utc_now()))
        for entry in reversed(self.verify()):
            if entry["subject"] == subject and entry["control"] == control:
                signed_at = str(entry["signed_at"])
                age = current - datetime.fromisoformat(signed_at)
                if age < timedelta():
                    return "future_signoff", signed_at
                return ("active" if age < LAPSE else "lapsed"), signed_at
        return "no_signoff", None
