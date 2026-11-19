from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from controlguard.inputs import Fields, decode, fields, items, string

REVISIONS = {
    "Qwen/Qwen3-0.6B": "c1899de289a04d12100db370d81485cdf75e47ca",
    "Qwen/Qwen3-8B": "b968826d9c46dd6066d109eabc6255188de91218",
    "Qwen/Qwen3-32B": "9216db5781bf21249d130ec9da846c4624c16137",
}
BANNED = ("qwen2.5-3b", "qwen2.5-72b", "codestral-22b")
TEMPLATE_SHA256 = "a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8"
TEMPLATE_GADGET = re.compile(r"__|os\s*\.\s*popen|subprocess|\b(?:import|include|extends)\b", re.I)


@dataclass(frozen=True)
class ModelSpec:
    repo: str
    revision: str

    def validate(self) -> None:
        if any(name in self.repo.lower() for name in BANNED):
            raise ValueError("This model is blocked from commercial use.")
        if re.fullmatch(r"[0-9a-f]{40}", self.revision) is None or REVISIONS.get(self.repo) != self.revision:
            raise ValueError("Use an allowlisted Qwen model and its pinned revision.")


def scan_template(template: str) -> None:
    if TEMPLATE_GADGET.search(template):
        raise ValueError("The chat template contains a blocked token.")
    if hashlib.sha256(template.encode()).hexdigest() != TEMPLATE_SHA256:
        raise ValueError("The chat template does not match the reviewed Qwen template.")


def tensor_offsets(record: Fields) -> tuple[int, int]:
    values = items(record.get("data_offsets"), "tensor data_offsets")
    if len(values) != 2:
        raise ValueError("Expected two tensor offsets.")
    start, end = values
    if (type(start) is not int or type(end) is not int or start < 0 or end < start):
        raise ValueError("Invalid tensor offsets.")
    return start, end


def verify_tensor(path: Path) -> None:
    with path.open("rb") as stream:
        first = stream.read(8)
        if len(first) != 8:
            raise ValueError("Safetensors file has no complete header.")
        size = int.from_bytes(first, "little")
        if not 2 <= size <= 100_000_000 or size > path.stat().st_size - 8:
            raise ValueError("Invalid safetensors header size.")
        header = decode(stream.read(size).decode("utf-8"))
        offsets = sorted(tensor_offsets(fields(metadata, name))
                         for name, metadata in header.items() if name != "__metadata__")
        cursor = 0
        for start, end in offsets:
            if start != cursor:
                raise ValueError("Safetensors offsets overlap or contain an unindexed gap.")
            cursor = end
        if cursor != path.stat().st_size - 8 - size or not offsets:
            raise ValueError("Safetensors offsets do not cover its payload.")


def verify_snapshot(path: Path) -> None:
    if any(child.suffix.lower() in {".bin", ".pt", ".pkl", ".pickle", ".pth"}
           for child in path.iterdir()):
        raise ValueError("The model snapshot contains an unsafe weight format.")
    tokenizer = decode((path / "tokenizer_config.json").read_text(encoding="utf-8"))
    scan_template(string(tokenizer.get("chat_template"), "chat_template"))
    shards = sorted(path.glob("*.safetensors"))
    if not shards:
        raise ValueError("The model snapshot has no safetensors weights.")
    for shard in shards:
        verify_tensor(shard)
