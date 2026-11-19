import argparse
from base64 import b64encode
from io import BytesIO
from pathlib import Path
import shlex
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]

WORKER = '''# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = [
#   "torch==2.7.1", "transformers==4.56.2", "trl==0.23.1",
#   "peft==0.17.1", "datasets==4.0.0", "bitsandbytes==0.47.0",
# ]
# ///
from base64 import b64decode
from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from huggingface_hub import HfApi

api = HfApi()
adapter, destination = sys.argv[1:3]
api.create_repo(destination, private=True, repo_type="model", exist_ok=True)
if not api.repo_info(destination, repo_type="model").private:
    raise ValueError("Refusing to upload to a public repository.")
with TemporaryDirectory() as temp:
    root = Path(temp)
    with ZipFile(BytesIO(b64decode(BUNDLE))) as archive:
        archive.extractall(root)
    sys.path.insert(0, temp)
    from controlguard.inputs import decode
    from controlguard.llm.dataset import generate
    from controlguard.llm.train import train

    data = root / "data"
    output = root / "output"
    generate(data, 2000, 64)
    config = decode((root / f"llm-config/qwen8b-{adapter}.json").read_text(encoding="utf-8"))
    train(config, data, output)
    api.upload_folder(repo_id=destination, repo_type="model", path_in_repo=adapter,
                      folder_path=output, ignore_patterns=["trainer/**"])
'''


def bundle() -> str:
    source = sorted((ROOT / "controlguard").rglob("*.py"))
    source += sorted((ROOT / "controlguard").glob("*.json"))
    source += sorted((ROOT / "llm-config").glob("qwen8b-*.json"))
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path in source:
            archive.write(path, path.relative_to(ROOT))
    return b64encode(buffer.getvalue()).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one private Qwen3-8B QLoRA job.")
    parser.add_argument("--adapter", required=True, choices=("a1", "a2"))
    parser.add_argument("--private-model-repo", required=True, metavar="OWNER/REPO")
    parser.add_argument("--launch", action="store_true", help="Start paid GPU compute.")
    args = parser.parse_args()
    parts = args.private_model_repo.split("/")
    if len(parts) != 2 or not all(parts):
        parser.error("Name a private model repository as OWNER/REPO.")
    command = ["hf", "jobs", "uv", "run", "--flavor", "a10g-large", "--timeout", "4h", "-s",
               "HF_TOKEN", "--python", "3.11"]
    print("Estimate: 1–3 hours per adapter, $1.50–$4.50 at $1.50/hour; 4-hour cap ($6).")
    if not args.launch:
        print("Prepared only. No job launched.")
        print(shlex.join([*command, "<bundled worker>", args.adapter, args.private_model_repo]))
        return
    with TemporaryDirectory() as temp:
        script = Path(temp) / "controlguard_job.py"
        slot = "from base64 import b64decode"
        worker = WORKER.replace(slot, f"BUNDLE = {bundle()!r}\n\n{slot}", 1)
        script.write_text(worker, encoding="utf-8")
        subprocess.run([*command, str(script), args.adapter, args.private_model_repo], check=True)


if __name__ == "__main__":
    main()
