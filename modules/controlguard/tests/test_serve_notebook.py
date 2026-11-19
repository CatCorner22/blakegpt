from io import BytesIO
import json
from pathlib import Path
from socket import AF_UNIX, SOCK_STREAM, socket
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request

import pytest

from controlguard.inputs import encode, fields, items, string
from scripts.serve_notebook import INSTALL, SMOKE, TAILSCALE, notebook

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


def test_tailscale_uses_a_state_directory_and_prints_the_http_url(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    socket_path = tmp_path / "tailscaled.sock"
    state_dir = tmp_path / "tailscale"
    status = ["tailscale", f"--socket={socket_path}", "status", "--json"]
    commands: list[list[str]] = []

    def launch(command: list[str], **options: object) -> None:
        assert command == [
            "tailscaled", "--tun=userspace-networking", f"--socket={socket_path}",
            f"--statedir={state_dir}",
        ]
        assert state_dir.is_dir()
        assert options["stdout"] is not None
        with socket(AF_UNIX, SOCK_STREAM) as listener:
            listener.bind(str(socket_path))

    def run(command: list[str], *, check: bool) -> None:
        assert check
        commands.append(command)

    def check_output(command: list[str]) -> bytes:
        assert command == status
        return b'{"BackendState":"Running","Self":{"DNSName":"controlguard-colab.example.ts.net."}}'

    fake_process = SimpleNamespace(Popen=launch, run=run, check_output=check_output, STDOUT=-2)
    with patch("shutil.which", return_value="/usr/bin/tailscaled"):
        exec(TAILSCALE, {"runtime": tmp_path, "subprocess": fake_process, "json": json,
                         "userdata": SimpleNamespace(get=lambda _: "test-auth-key")})
    assert commands == [
        status[:2] + ["serve", "--bg", "--http=80", "--yes", "http://127.0.0.1:8000"],
    ]
    assert "CONTROLGUARD_BASE_URL=http://controlguard-colab.example.ts.net/v1" in capsys.readouterr().out


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
        assert payload["messages"][0] == {
            "role": "system",
            "content": "Pick exactly one tool and copy only facts provided by the user. "
                       "Do not calculate, guess missing inputs, attest to controls, or "
                       "answer in prose. If facts are missing, return no tool call.",
        }
        assert payload["messages"][1]["role"] == "user"
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
