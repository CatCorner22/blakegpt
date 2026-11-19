from io import BytesIO
import json
from pathlib import Path
from urllib.request import Request

import pytest

from controlguard.inputs import encode, fields, items, string
from scripts.serve_notebook import SMOKE, notebook

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
