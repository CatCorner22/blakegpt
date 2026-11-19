from base64 import b64decode
from pathlib import Path
import os
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

from controlguard.inputs import decode, fields, items, string

ROOT = Path(__file__).resolve().parents[1]


def notebook_cells(path: str) -> list[object]:
    notebook = decode((ROOT / path).read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    return items(notebook["cells"], "cells")


def code_for(cell: dict[str, object]) -> str:
    lines = items(cell["source"], "source")
    assert all(isinstance(line, str) for line in lines)
    return "".join(map(str, lines))


@pytest.mark.parametrize("path", ("llm/colab/train_adapters.ipynb", "kaggle/train_adapters.ipynb"))
def test_notebook_cpu_preflight_and_code_syntax(path: str, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    names: dict[str, object] = {"RUNTIME_ROOT": str(runtime)}
    found: set[str] = set()
    for value in notebook_cells(path):
        cell = fields(value)
        if cell["cell_type"] != "code":
            continue
        identifier = string(cell["id"], "cell id")
        found.add(identifier)
        compiled = compile(code_for(cell), f"{path}:{identifier}", "exec")
        if identifier in ("settings", "source"):
            exec(compiled, names)
            if identifier == "settings" and path.startswith("llm/colab/"):
                assert names["project_source"] == "GitHub"
                names["project_source"] = "Embedded"
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


def test_colab_private_clone_uses_ephemeral_auth_and_drive_fallback(tmp_path: Path) -> None:
    path = "llm/colab/train_adapters.ipynb"
    source = next(fields(cell) for cell in notebook_cells(path) if fields(cell).get("id") == "source")
    code = compile(code_for(source), f"{path}:source", "exec")
    colab = ModuleType("google.colab")
    setattr(colab, "userdata", SimpleNamespace(get=lambda name: {"GITHUB_TOKEN": "test-secret"}[name]))
    mounted: list[str] = []
    setattr(colab, "drive", SimpleNamespace(mount=mounted.append))
    names: dict[str, object] = {"RUNTIME_ROOT": str(tmp_path), "project_source": "GitHub"}

    def clone(args: list[str], *, env: dict[str, str], stdout: int, stderr: int) -> subprocess.CompletedProcess[str]:
        repo = "https://github.com/CatCorner22/controlguard.git"
        assert args[-2] == repo and "test-secret" not in " ".join(args)
        assert env["GIT_CONFIG_KEY_0"] == f"http.{repo}.extraHeader"
        assert b64decode(env["GIT_CONFIG_VALUE_0"].split()[-1]) == b"x-access-token:test-secret"
        assert stdout == stderr == subprocess.DEVNULL
        return subprocess.CompletedProcess(args, 128)

    with patch.dict("sys.modules", {"google.colab": colab}), patch("subprocess.run", side_effect=clone):
        with pytest.raises(RuntimeError, match="select Drive"):
            exec(code, names)
        assert names["token"] is None and names["credential"] is None
        assert "GIT_CONFIG_VALUE_0" not in fields(names["clone_env"])
        names.update(project_source="Drive", project_folder="Uploaded ControlGuard")
        with pytest.raises(FileNotFoundError, match="root of a ControlGuard checkout"):
            exec(code, names)
    assert mounted == ["/content/drive"]
    assert names["source"] == Path("/content/drive/MyDrive/Uploaded ControlGuard")


@pytest.mark.parametrize("path", ("llm/colab/train_adapters.ipynb", "kaggle/train_adapters.ipynb"))
def test_training_cell_shows_worker_stderr(path: str, tmp_path: Path,
                                          capsys: pytest.CaptureFixture[str]) -> None:
    cell = next(fields(value) for value in notebook_cells(path) if fields(value).get("id") == "training")
    config = tmp_path / "llm-config"
    config.mkdir()
    (config / "kaggle-a1.json").write_text("{}", encoding="utf-8")
    package = tmp_path / "controlguard" / "llm"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").touch()
    (package / "__init__.py").touch()
    (package / "train.py").write_text('raise ValueError("visible worker failure")\n', encoding="utf-8")
    names = {"source": tmp_path, "output": tmp_path / "output", "runtime_root": tmp_path,
             "adapters": ("a1",), "base": "Qwen3-8B", "steps": 1, "eval_examples": 1,
             "subprocess": subprocess, "sys": sys, "env": os.environ, "data": tmp_path}
    with pytest.raises(subprocess.CalledProcessError) as error:
        exec(compile(code_for(cell), f"{path}:training", "exec"), names)
    assert error.value.returncode == 1
    assert "ValueError: visible worker failure" in capsys.readouterr().out


def test_kaggle_metadata_targets_private_t4() -> None:
    metadata = decode((ROOT / "kaggle/kernel-metadata.json").read_text(encoding="utf-8"))
    assert metadata["is_private"] is True and metadata["enable_gpu"] is True
    assert metadata["machine_shape"] == "NvidiaTeslaT4"
    assert (ROOT / "kaggle" / string(metadata["code_file"], "code_file")).exists()
