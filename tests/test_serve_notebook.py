from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request

import pytest

from controlguard.inputs import encode, fields, items, string
from scripts.serve_notebook import INSTALL, SMOKE, notebook

ROOT = Path(__file__).resolve().parents[1]


def test_serve_notebook_matches_generator_and_has_valid_python() -> None:
    generated = notebook()
    saved = (ROOT / "llm/colab/serve_combined.ipynb").read_text(encoding="utf-8")
    assert saved == encode(generated, pretty=True) + "\n"
    for value in items(generated["cells"], "cells"):
        cell = fields(value)
        if cell["cell_type"] == "code":
            lines = items(cell["source"], "source")
            assert all(isinstance(line, str) for line in lines)
            compile("".join(map(str, lines)), string(cell["id"], "id"), "exec")


def test_install_uses_uv_without_ensurepip() -> None:
    commands: list[list[str]] = []

    def run(command: list[str], *, check: bool) -> None:
        assert check
        commands.append(command)

    sys_python = "/usr/bin/python3.13"
    venv = "/content/controlguard-serve/venv"
    python = f"{venv}/bin/python"
    exec(INSTALL, {"Path": Path, "sys": SimpleNamespace(executable=sys_python),
                   "subprocess": SimpleNamespace(run=run)})

    uv = [sys_python, "-m", "uv"]
    assert len(commands) == 4
    assert commands[0] == [sys_python, "-m", "pip", "install", "uv"]
    assert commands[1] == uv + ["venv", "--seed", "--python", sys_python, venv]
    assert commands[2][:-1] == uv + [
        "pip", "install", "--python", python, "--index-strategy", "unsafe-best-match",
        "--no-cache", "--extra-index-url", "https://download.pytorch.org/whl/cu130",
        "torch==2.14.0+cu130",
    ]
    assert commands[2][-1].endswith("vllm-0.34.0-cp38-abi3-manylinux_2_28_x86_64.whl")
    assert commands[3][:2] == [python, "-c"]


@pytest.mark.parametrize("structured", [True, False])
def test_smoke_requires_a_structured_leave_tool_call(structured: bool) -> None:
    def endpoint(request: Request, timeout: int) -> BytesIO:
        assert timeout == 60
        assert request.full_url == "http://127.0.0.1:8000/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer test-key"
        assert isinstance(request.data, bytes)
        payload = json.loads(request.data)
        assert payload["model"] == "combined"
        assert payload["tool_choice"] == "auto"
        assert payload["tools"][0]["function"]["name"] == "leave"
        function = {"name": "leave", "arguments": '{"text":"3 days of PTO","shift_hours":8}'}
        message = ({"tool_calls": [{"type": "function", "function": function}]} if structured
                   else {"content": json.dumps(function)})
        return BytesIO(json.dumps({"choices": [{"message": message}]}).encode())

    names = {"json": json, "urlopen": endpoint, "Request": Request,
             "local_url": "http://127.0.0.1:8000", "api_key": "test-key"}
    if structured:
        exec(SMOKE, names)
    else:
        with pytest.raises(RuntimeError, match="Expected one structured leave tool call"):
            exec(SMOKE, names)
