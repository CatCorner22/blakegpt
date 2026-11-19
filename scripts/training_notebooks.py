import argparse
from pathlib import Path
import re
import textwrap

from controlguard.inputs import Fields, encode
from scripts.hf_job import ROOT, bundle

COLAB_SOURCE = '''# @title Clone ControlGuard or use a Drive checkout
from pathlib import Path

runtime_root = Path(globals().get("RUNTIME_ROOT", "/content/controlguard-training"))
runtime_root.mkdir(parents=True, exist_ok=True)

if project_source == "GitHub":
    from base64 import b64encode
    import os
    import subprocess
    from tempfile import mkdtemp
    from google.colab import userdata

    try:
        token = userdata.get("GITHUB_TOKEN")
    except (userdata.SecretNotFoundError, userdata.NotebookAccessError):
        token = None
    clone_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "0"}
    if token:
        credential = b64encode(f"x-access-token:{token}".encode()).decode()
        clone_env.update({
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/CatCorner22/controlguard.git.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {credential}",
        })
    source = Path(mkdtemp(prefix="checkout-", dir=runtime_root))
    try:
        result = subprocess.run([
            "git", "-c", "http.followRedirects=false", "clone", "--depth", "1", "--branch", "main",
            "https://github.com/CatCorner22/controlguard.git", str(source),
        ], env=clone_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        clone_env.pop("GIT_CONFIG_VALUE_0", None)
        token = credential = None
    if result.returncode != 0:
        raise RuntimeError(
            "Clone failed. Grant this notebook access to the GITHUB_TOKEN Colab secret "
            "with read access to CatCorner22/controlguard, or select Drive in Training settings."
        )
elif project_source == "Drive":
    from google.colab import drive

    folder = Path(project_folder)
    if not project_folder.strip() or folder.is_absolute() or ".." in folder.parts:
        raise ValueError("Enter a checkout folder relative to My Drive.")
    drive.mount("/content/drive")
    source = Path("/content/drive/MyDrive") / folder
elif project_source != "Embedded":
    raise ValueError("Choose GitHub, Drive, or Embedded as the project source.")
'''

PREFLIGHT = """import os
import subprocess
import sys

if base not in ("Qwen3-8B", "Qwen3-32B") or adapter not in ("A1", "A2", "both"):
    raise ValueError("Choose a listed base and adapter.")
if not 1 <= steps <= 250 or not 1 <= eval_examples <= 32:
    raise ValueError("Use 1–250 steps and 1–32 evaluation examples.")
try:
    report = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,name,memory.total,compute_cap", "--format=csv,noheader,nounits"],
        text=True, capture_output=True, check=True,
    ).stdout
except (FileNotFoundError, subprocess.CalledProcessError) as error:
    raise RuntimeError("Select a GPU runtime before running the training cells.") from error
minimum_mib = 39000 if base == "Qwen3-32B" else 14000
selected = None
for line in report.strip().splitlines():
    index, name, memory, capability = (field.strip() for field in line.split(","))
    if int(memory) >= minimum_mib and float(capability) >= (8.0 if base == "Qwen3-32B" else 7.0):
        selected = (index, name, memory)
        break
if selected is None:
    raise RuntimeError(f"{base} needs a supported GPU with at least {minimum_mib} MiB. Use T4/L4 for 8B or A100 40 GB for 32B.")
env = {**os.environ, "CUDA_VISIBLE_DEVICES": selected[0], "TOKENIZERS_PARALLELISM": "false"}
print(f"Using one {selected[1]} with {selected[2]} MiB.")
"""

INSTALL = """packages = [
    "unsloth==2026.11.6", "unsloth_zoo==2026.11.6", "transformers==4.56.2",
    "trl==0.23.1", "peft==0.18.0", "datasets==4.3.0", "bitsandbytes==0.50.2",
]
subprocess.run([sys.executable, "-m", "pip", "install", "-q", *packages], check=True)
"""

DATA = """if dataset_folder.strip():
    data = Path(dataset_folder).expanduser().resolve()
else:
    data = runtime_root / "data"
    subprocess.run([
        sys.executable, "-m", "controlguard.llm.dataset", "--output", str(data),
        "--train-count", "512", "--eval-count", "32",
    ], cwd=source, check=True)
adapters = ("a1", "a2") if adapter == "both" else (adapter.lower(),)
for family in adapters:
    for split in ("train", "eval"):
        if not (data / f"{family}-{split}.jsonl").is_file():
            raise FileNotFoundError(f"Missing {family}-{split}.jsonl in {data}.")
"""

TRAIN = """import json

output.mkdir(parents=True, exist_ok=True)
for family in adapters:
    config_path = f"kaggle-{family}" if base == "Qwen3-8B" else f"qwen32b-{family}"
    config = json.loads((source / "llm-config" / f"{config_path}.json").read_text())
    config.update(mode="unsloth-qlora", steps=steps, eval_limit=eval_examples, max_length=1024)
    job_config = runtime_root / f"{family}-resolved.json"
    target = output / base / family
    job_config.write_text(json.dumps(config, allow_nan=False))
    command = [
        sys.executable, "-u", "-m", "controlguard.llm.train", str(job_config),
        "--data", str(data), "--output", str(target),
    ]
    with subprocess.Popen(command, cwd=source, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, errors="replace") as worker:
        for line in worker.stdout:
            print(line, end="", flush=True)
        return_code = worker.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, command)
    weights = target / "adapter" / "adapter_model.safetensors"
    if not weights.is_file():
        raise FileNotFoundError(f"No saved safetensors adapter at {weights}.")
    print(f"{family.upper()} weights: {weights}")
    print((target / "metrics.json").read_text())
"""


def cell(kind: str, source: str, identifier: str) -> Fields:
    result: Fields = {"cell_type": kind, "id": identifier, "metadata": {},
                      "source": source.splitlines(keepends=True)}
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


def notebook(platform: str, content: str) -> Fields:
    colab = platform == "colab"
    location = "/content/controlguard-training" if colab else "/kaggle/working/controlguard-training"
    title = "# ControlGuard: train A1 and A2 on Colab Pro\n" if colab else "# ControlGuard: Kaggle free-tier adapter training\n"
    intro = (title + ("Select L4 or A100 for 8B. Select A100 40 GB for 32B. "
                     "The notebook writes adapter weights and metrics to Google Drive.\n" if colab else
                     "Select the T4 accelerator, not P100. The notebook uses one GPU at a time. "
                     "Find both adapters in this notebook's outputs.\n")
             + "The notebook supplies the project source and can generate synthetic data. "
             "To use pre-generated data, upload the JSONL files and enter their directory. "
             "Do not upload private company or employee data. The notebook uses no Gemini API.\n")
    if colab:
        params = '''# @title Training settings
base = "Qwen3-8B" # @param ["Qwen3-8B", "Qwen3-32B"]
adapter = "both" # @param ["A1", "A2", "both"]
steps = 40 # @param {type:"integer"}
eval_examples = 8 # @param {type:"integer"}
dataset_folder = "" # @param {type:"string"}
project_source = "GitHub" # @param ["GitHub", "Drive", "Embedded"]
project_folder = "ControlGuard" # @param {type:"string"}
drive_folder = "ControlGuard-Adapters" # @param {type:"string"}
'''
        setup_output = '''from google.colab import drive

folder = Path(drive_folder)
if not drive_folder.strip() or folder.is_absolute() or ".." in folder.parts:
    raise ValueError("Use a folder name within My Drive.")
drive.mount("/content/drive")
output = Path("/content/drive/MyDrive") / folder
'''
    else:
        params = '''base = "Qwen3-8B"
adapter = "both"
steps = 40
eval_examples = 8
dataset_folder = ""
project_folder = ""
'''
        setup_output = 'output = Path("/kaggle/working/controlguard-adapters")\n'
    chunks = "\n".join(f'    "{line}"' for line in textwrap.wrap(content, 120))
    bootstrap = f'''# Unpack the source bundle that this repository's packager supplies.
from base64 import b64decode
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

runtime_root = Path(globals().get("RUNTIME_ROOT", "{location}"))
runtime_root.mkdir(parents=True, exist_ok=True)
bundle_text = (
{chunks}
)
if project_folder.strip():
    source = Path(project_folder).expanduser().resolve()
    if not (source / "controlguard/llm/train.py").is_file() or not (source / "llm-config").is_dir():
        raise FileNotFoundError("Use the root of an uploaded or cloned ControlGuard checkout.")
else:
    source = runtime_root / "source"
    source.mkdir(exist_ok=True)
    with ZipFile(BytesIO(b64decode(bundle_text))) as archive:
        archive.extractall(source)
print("ControlGuard source ready.")
'''
    if colab:
        bootstrap = COLAB_SOURCE + f'''else:
    from base64 import b64decode
    from io import BytesIO
    from zipfile import ZipFile

    source = runtime_root / "source"
    source.mkdir(exist_ok=True)
    bundle_text = (
{textwrap.indent(chunks, "    ")}
    )
    with ZipFile(BytesIO(b64decode(bundle_text))) as archive:
        archive.extractall(source)
if not (source / "controlguard/llm/train.py").is_file() or not (source / "llm-config").is_dir():
    raise FileNotFoundError("Use the root of a ControlGuard checkout.")
print("ControlGuard source ready.")
'''
    cells = [cell("markdown", intro, "intro"), cell("code", params, "settings"),
             cell("code", bootstrap, "source"), cell("code", PREFLIGHT, "gpu-preflight"),
             cell("code", setup_output, "output"),
             cell("code", INSTALL, "dependencies"), cell("code", DATA, "datasets"),
             cell("code", TRAIN, "training")]
    info: Fields = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python"}}
    if colab:
        info.update(colab={"provenance": []}, accelerator="GPU")
    return {"cells": cells, "metadata": info, "nbformat": 4, "nbformat_minor": 5}


def write_notebooks(kaggle_owner: str) -> None:
    content = bundle("*.json")
    for platform, target in (("colab", ROOT / "llm/colab/train_adapters.ipynb"),
                             ("kaggle", ROOT / "kaggle/train_adapters.ipynb")):
        target.write_text(encode(notebook(platform, content), pretty=True) + "\n", encoding="utf-8")
    metadata = {
        "id": f"{kaggle_owner}/controlguard-qlora", "title": "ControlGuard QLoRA",
        "code_file": "train_adapters.ipynb", "language": "python", "kernel_type": "notebook",
        "is_private": True, "enable_gpu": True, "enable_internet": True, "machine_shape": "NvidiaTeslaT4",
        "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": [],
    }
    (ROOT / "kaggle/kernel-metadata.json").write_text(encode(metadata, pretty=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare standalone Colab and Kaggle notebooks. Do not launch them.")
    parser.add_argument("--kaggle-owner", default="YOUR_KAGGLE_USERNAME")
    args = parser.parse_args()
    if re.fullmatch(r"[A-Za-z0-9_-]+", args.kaggle_owner) is None:
        parser.error("Use a Kaggle username.")
    write_notebooks(args.kaggle_owner)
    print("Wrote the Colab and Kaggle notebooks. No job launched.")


if __name__ == "__main__":
    main()
