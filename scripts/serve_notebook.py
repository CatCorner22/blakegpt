from controlguard.inputs import Fields, encode
from scripts.hf_job import ROOT
from scripts.training_notebooks import cell

SETUP = '''# @title Check the L4 and load your adapter
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import Request, urlopen

from google.colab import drive, userdata

gpu = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                     capture_output=True, text=True)
if gpu.returncode or gpu.stdout.strip() != "NVIDIA L4":
    raise RuntimeError("Select one L4 GPU in Colab before running this notebook.")

api_key = userdata.get("CONTROLGUARD_API_KEY")
if not api_key or not api_key.strip():
    raise ValueError("Set a nonempty CONTROLGUARD_API_KEY in Colab Secrets.")
drive.mount("/content/drive")
adapter = Path("/content/drive/MyDrive/ControlGuard-Adapters/Qwen3-8B/combined/adapter")
if not (adapter / "adapter_model.safetensors").is_file():
    raise FileNotFoundError(f"Train or copy the combined adapter to {adapter}.")
rank = json.loads((adapter / "adapter_config.json").read_text())["r"]
if type(rank) is not int or not 1 <= rank <= 512:
    raise ValueError("The adapter rank must be an integer from 1 to 512.")
max_rank = next(limit for limit in (1, 8, 16, 32, 64, 128, 256, 320, 512) if limit >= rank)
'''

INSTALL = '''# @title Install vLLM in an isolated environment
runtime = Path("/content/controlguard-serve")
venv = runtime / "venv"
subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)
uv = [sys.executable, "-m", "uv"]
subprocess.run(uv + ["venv", "--seed", "--python", sys.executable, str(venv)], check=True)
python = str(venv / "bin/python")
wheel = ("https://wheels.vllm.ai/62d4bc3c7e33b1b6c906e233e6af2d3506c482ca/"
         "vllm-0.34.0-cp38-abi3-manylinux_2_28_x86_64.whl")
subprocess.run(uv + ["pip", "install", "--python", python, "--index-strategy",
                "unsafe-best-match", "--no-cache",
                "--extra-index-url", "https://download.pytorch.org/whl/cu130",
                "torch==2.14.0+cu130", wheel], check=True)
subprocess.run([python, "-c", "import torch, vllm; "
                "assert torch.version.cuda == '13.0' and torch.cuda.is_available(); "
                "print('vLLM', vllm.__version__, '| Torch', torch.__version__)"], check=True)
'''

START = '''# @title Start the model on port 8000
local_url = "http://127.0.0.1:8000"
if "server" in globals() and server.poll() is None:
    server.terminate()
    server.wait(timeout=30)

log = runtime / "vllm.log"
with log.open("w") as output:
    server = subprocess.Popen([
        str(venv / "bin/vllm"), "serve", "Qwen/Qwen3-8B",
        "--revision", "b968826d9c46dd6066d109eabc6255188de91218",
        "--host", "127.0.0.1", "--port", "8000", "--dtype", "bfloat16",
        "--max-model-len", "4096", "--max-num-seqs", "2",
        "--gpu-memory-utilization", "0.92", "--enforce-eager",
        "--enable-lora", "--lora-modules", f"combined={adapter}", "--max-lora-rank", str(max_rank),
        "--enable-auto-tool-choice", "--tool-call-parser", "hermes",
        "--default-chat-template-kwargs", '{"enable_thinking": false}', "--api-key", api_key,
    ], env={**os.environ, "VLLM_LOGGING_LEVEL": "WARNING"}, stdout=output, stderr=subprocess.STDOUT)

deadline = monotonic() + 1200
while monotonic() < deadline and server.poll() is None:
    try:
        request = Request(f"{local_url}/v1/models", headers={"Authorization": f"Bearer {api_key}"})
        with urlopen(request, timeout=3) as response:
            if any(model["id"] == "combined" for model in json.load(response)["data"]):
                print("The combined adapter is ready.")
                break
    except URLError:
        pass
    sleep(3)
else:
    if server.poll() is None:
        server.terminate()
    raise RuntimeError(f"The model did not start. Check {log} in the private runtime.")
'''

TAILSCALE = '''# @title Share the model privately over Tailscale
from shutil import which

auth_key = userdata.get("TS_AUTHKEY")
if not auth_key:
    raise ValueError("Add TS_AUTHKEY to Colab Secrets.")
if not which("tailscaled"):
    subprocess.run(["bash", "-o", "pipefail", "-c", "curl -fsSL https://tailscale.com/install.sh | sh"],
                   check=True)

socket = runtime / "tailscaled.sock"
ts = ["tailscale", f"--socket={socket}"]
if "tailscaled" not in globals() or tailscaled.poll() is not None:
    state_dir = runtime / "tailscale"
    state_dir.mkdir(mode=0o700, exist_ok=True)
    with (runtime / "tailscaled.log").open("w") as output:
        tailscaled = subprocess.Popen([
            "tailscaled", "--tun=userspace-networking", f"--socket={socket}",
            f"--statedir={state_dir}",
        ], stdout=output, stderr=subprocess.STDOUT)
    for _ in range(30):
        if socket.is_socket():
            break
        sleep(1)
    else:
        raise RuntimeError("Tailscale did not start. Check tailscaled.log in the runtime.")

status = json.loads(subprocess.check_output(ts + ["status", "--json"]))
if status["BackendState"] != "Running":
    with NamedTemporaryFile(mode="w") as key_file:
        key_file.write(auth_key)
        key_file.flush()
        subprocess.run(ts + ["up", f"--auth-key=file:{key_file.name}",
                             "--hostname=controlguard-colab", "--timeout=60s"], check=True)
del auth_key
subprocess.run(ts + ["serve", "--bg", "--http=80", "--yes", "http://127.0.0.1:8000"], check=True)
status = json.loads(subprocess.check_output(ts + ["status", "--json"]))
dns = status["Self"]["DNSName"].rstrip(".")
base_url = f"http://{dns}/v1"
print(f"CONTROLGUARD_BASE_URL={base_url}")
print("CONTROLGUARD_MODEL=combined")
print("CONTROLGUARD_API_KEY: use the value from Colab Secrets.")
'''

SMOKE = '''# @title Check that the model returns a structured tool call
leave_tool = {
    "type": "function",
    "function": {
        "name": "leave", "description": "Replace leave in days with hours.",
        "parameters": {"type": "object", "required": ["text"], "properties": {
            "text": {"type": "string"}, "shift_hours": {"type": "number"},
        }},
    },
}
payload = {
    "model": "combined", "tool_choice": "auto", "tools": [leave_tool],
    "messages": [
        {"role": "system", "content": "Pick exactly one tool and copy only facts provided by the user. "
                                      "Do not calculate, guess missing inputs, attest to controls, or "
                                      "answer in prose. If facts are missing, return no tool call."},
        {"role": "user", "content": "Convert this leave clause to hours: 3 days of PTO. "
                                    "Use 8 hours per shift."},
    ],
    "temperature": 0, "max_tokens": 256,
}
request = Request(f"{local_url}/v1/chat/completions", data=json.dumps(payload).encode(),
                  headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
with urlopen(request, timeout=60) as response:
    calls = json.load(response)["choices"][0]["message"].get("tool_calls") or []
if len(calls) != 1 or calls[0]["type"] != "function" or calls[0]["function"]["name"] != "leave":
    raise RuntimeError("Expected one structured leave tool call.")
args = json.loads(calls[0]["function"]["arguments"])
if not isinstance(args, dict) or not isinstance(args.get("text"), str) or not args["text"].strip():
    raise RuntimeError("The leave tool call is missing its text input.")
print("Smoke test passed: combined returned a structured leave tool call.")
'''


def notebook() -> Fields:
    intro = """# Serve the combined ControlGuard adapter
Select an **L4 GPU** in Colab. Add `TS_AUTHKEY` and `CONTROLGUARD_API_KEY` to Colab Secrets
and grant this notebook access. Use a strong random API key and keep it private.

Enable MagicDNS in Tailscale. The Precog host must join the same tailnet and have access
to the Colab node on port 80. Use a short-lived, ephemeral auth key for the Colab node.
This notebook uses HTTP over the encrypted tailnet with private Tailscale Serve, not public Funnel.

Run the cells in order. The model stops when Colab ends the runtime. Disconnect and
delete the runtime when finished to stop using GPU units. Use synthetic text for this test.
"""
    return {
        "cells": [cell("markdown", intro, "intro"), cell("code", SETUP, "setup"),
                  cell("code", INSTALL, "install"), cell("code", START, "serve"),
                  cell("code", TAILSCALE, "tailscale"), cell("code", SMOKE, "smoke")],
        "metadata": {"colab": {"provenance": []}, "accelerator": "GPU",
                     "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


if __name__ == "__main__":
    target = ROOT / "llm/colab/serve_combined.ipynb"
    target.write_text(encode(notebook(), pretty=True) + "\n", encoding="utf-8")
    print(f"Wrote {target}. No GPU job launched.")
