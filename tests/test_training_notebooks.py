from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from controlguard.inputs import decode, fields, items, string

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", ("llm/colab/train_adapters.ipynb", "kaggle/train_adapters.ipynb"))
def test_notebook_cpu_preflight_and_code_syntax(path: str, tmp_path: Path) -> None:
    source = (ROOT / path).read_text(encoding="utf-8")
    notebook = decode(source)
    assert notebook["nbformat"] == 4
    runtime = tmp_path / "runtime"
    names: dict[str, object] = {"RUNTIME_ROOT": str(runtime)}
    found: set[str] = set()
    for value in items(notebook["cells"], "cells"):
        cell = fields(value)
        if cell["cell_type"] != "code":
            continue
        identifier = string(cell["id"], "cell id")
        found.add(identifier)
        lines = items(cell["source"], "source")
        assert all(isinstance(line, str) for line in lines)
        code = "".join(map(str, lines))
        compiled = compile(code, f"{path}:{identifier}", "exec")
        if identifier in ("settings", "source"):
            exec(compiled, names)
        elif identifier == "gpu-preflight":
            with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi")) as run:
                with pytest.raises(RuntimeError, match="Select a GPU runtime"):
                    exec(compiled, names)
                assert run.call_count == 1
            with patch("subprocess.run", return_value=subprocess.CompletedProcess(
                    ["nvidia-smi"], 0, "0, Tesla P100, 16280, 6.0\n1, Tesla T4, 15109, 7.5")):
                exec(compiled, names)
            assert fields(names["env"])["CUDA_VISIBLE_DEVICES"] == "1"
            if path.startswith("llm/colab/"):
                names["base"] = "Qwen3-32B"
                with patch("subprocess.run", return_value=subprocess.CompletedProcess(
                        ["nvidia-smi"], 0, "0, L4, 23034, 8.9")):
                    with pytest.raises(RuntimeError, match="A100 40 GB"):
                        exec(compiled, names)
                with patch("subprocess.run", return_value=subprocess.CompletedProcess(
                        ["nvidia-smi"], 0, "0, NVIDIA A100-SXM4-40GB, 40960, 8.0")):
                    exec(compiled, names)
                assert fields(names["env"])["CUDA_VISIBLE_DEVICES"] == "0"
    assert {"settings", "source", "gpu-preflight", "output", "dependencies", "datasets", "training"} == found
    assert (runtime / "source/controlguard/llm/train.py").read_bytes() == (
        ROOT / "controlguard/llm/train.py").read_bytes()
    assert (runtime / "source/llm-config/qwen32b-a2.json").is_file()


def test_kaggle_metadata_targets_private_t4() -> None:
    metadata = decode((ROOT / "kaggle/kernel-metadata.json").read_text(encoding="utf-8"))
    assert metadata["is_private"] is True and metadata["enable_gpu"] is True
    assert metadata["machine_shape"] == "NvidiaTeslaT4"
    assert (ROOT / "kaggle" / string(metadata["code_file"], "code_file")).exists()
