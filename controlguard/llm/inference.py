import http.client
import os
import re
from urllib.parse import urlsplit

from controlguard.app import DISCLAIMER, run_engine
from controlguard.inputs import Fields, decode, encode, fields, items, string
from controlguard.ledger import Ledger

from .tools import ADAPTERS, FINAL, SCHEMAS, SYSTEM, tools_for, validate
from .train import json_native

PII = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b|"
    r"\b(?:\d{3}[- ]\d{2}[- ]\d{4}|\d{9,19})\b|"
    r"(?<!\w)(?:\+1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}\b|"
    r"\b(?:ssn|routing(?: number)?|(?:bank )?account(?: number)?|tax id)\s*[:#=]\s*"
    r"(?:[\d*Xx][ -]?){4,22}|"
    r"\b\d{1,6}\s+(?:[A-Z0-9.'\-]+\s+){1,5}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Blvd|Boulevard|Way)\b\.?",
    re.IGNORECASE,
)
ADDRESS_LABEL = re.compile(r"\b(?:home|mailing|residential) address\s*[:=][^\r\n;]+", re.I)
IDENTITY_LABEL = re.compile(r"\b(?:full|employee|first|last|legal) name\s*[:=][^\r\n;,]+", re.I)


def scrub(text: str) -> str:
    for pattern in (ADDRESS_LABEL, IDENTITY_LABEL, PII):
        text = pattern.sub("[REDACTED]", text)
    return text


def scrub_object(value: object) -> object:
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_object(child) for child in items(value, "PII values")]
    if isinstance(value, dict):
        return {scrub(key): scrub_object(child) for key, child in fields(value).items()}
    return value


class LocalClient:
    def __init__(self, base_url: str, model: str) -> None:
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1")
                or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError("Use a local HTTP endpoint at 127.0.0.1 or [::1].")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.path = parsed.path.rstrip("/") + "/chat/completions"
        self.model = model

    def request(self, messages: list[Fields], adapter: str) -> Fields:
        payload: Fields = {
            "model": self.model, "messages": messages, "temperature": 0, "max_tokens": 512,
        }
        if messages[-1]["role"] == "tool":
            payload["response_format"] = {"type": "json_schema", "json_schema":
                                          {"name": "controlguard_status", "strict": True, "schema": FINAL}}
        else:
            payload.update(tools=tools_for(ADAPTERS[adapter]), tool_choice="auto")
        conn = http.client.HTTPConnection(self.host, self.port, timeout=30)
        try:
            conn.request("POST", self.path, body=encode(scrub_object(payload)).encode("utf-8"),
                         headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            if response.status != 200:
                raise ValueError(f"The local model returned HTTP {response.status}.")
            body = response.read(1_000_001)
        finally:
            conn.close()
        if len(body) > 1_000_000:
            raise ValueError("The local model response exceeded 1 MB.")
        choices = items(decode(body.decode("utf-8")).get("choices"), "choices")
        if not choices:
            raise ValueError("The local model did not return a choice.")
        return fields(fields(choices[0]).get("message"), "model message")


def execute(name: str, arguments: Fields, ledger: Ledger) -> Fields:
    validate(arguments, SCHEMAS[name])
    output = run_engine(name, arguments, ledger)
    if name == "policy" and output["passes_screen"] is True and output["title_valid"] is True:
        output.update({key: arguments[key] for key in ("title", "text") if key in arguments})
    return {"tool": name, "result": output}


def response(mode: str, status: str, results: list[Fields]) -> Fields:
    result: Fields = {"mode": mode, "status": status, "results": results, "disclaimer": DISCLAIMER}
    if status == "needs_input":
        result["next_step"] = "Add the missing facts or use the tool's JSON form."
    return result


def fallback(prompt: str, adapter: str, ledger: Ledger) -> Fields:
    name, _, raw = prompt.strip().partition(" ")
    if name in ADAPTERS[adapter] and raw.lstrip().startswith("{"):
        return response("rules", "complete", [execute(name, decode(raw), ledger)])
    if "leave" in ADAPTERS[adapter]:
        match = re.fullmatch(r"(?:convert(?: leave)?|check policy)\s*:\s*(.+)", prompt, re.I | re.S)
        if match:
            name = "leave" if prompt.lower().startswith("convert") else "policy"
            return response("rules", "complete", [execute(name, {"text": match[1]}, ledger)])
    return response("rules", "needs_input", [])


def ask(prompt: str, adapter: str, ledger: Ledger, client: LocalClient | None = None) -> Fields:
    if adapter not in ADAPTERS:
        raise ValueError("Choose policy and leave (A1), controls and pricing (A2), or combined.")
    if not 0 < len(prompt.strip()) <= 12_000:
        raise ValueError("Enter a request under 12,000 characters.")
    safe_prompt = scrub(prompt.strip())
    if client is None:
        return fallback(safe_prompt, adapter, ledger)
    messages: list[Fields] = [{"role": "system", "content": SYSTEM},
                              {"role": "user", "content": safe_prompt}]
    results: list[Fields] = []
    for _ in range(4):
        message = client.request(messages, adapter)
        returned = message.get("tool_calls")
        if not returned:
            final = decode(string(message.get("content"), "final model response"))
            validate(final, FINAL)
            status = "complete" if results and final["status"] == "complete" else "needs_input"
            return response("model", status, results)
        calls = items(returned, "tool calls")
        if len(calls) > 2 or len(results) + len(calls) > 4:
            raise ValueError("The model requested too many tools.")
        normalized: list[Fields] = []
        followups: list[Fields] = []
        for call in calls:
            obj = fields(call, "tool call")
            if obj.get("type") != "function":
                raise ValueError("The model requested a call other than a function.")
            function = fields(obj.get("function"), "function")
            name = string(function.get("name"), "function name")
            if name not in ADAPTERS[adapter]:
                raise ValueError("The model requested a tool outside this adapter.")
            arguments = decode(string(function.get("arguments"), "JSON arguments"))
            safe_arguments = fields(scrub_object(arguments))
            result = execute(name, safe_arguments, ledger)
            call_id = f"call_{len(results) + 1}"
            normalized.append({"id": call_id, "type": "function", "function": {
                "name": name, "arguments": encode(json_native(safe_arguments))}})
            followups.append({"role": "tool", "tool_call_id": call_id,
                              "content": encode(scrub_object(result))})
            results.append(result)
        messages.append({"role": "assistant", "content": None, "tool_calls": normalized})
        messages.extend(followups)
    return response("model", "needs_input", results)


def configured_client(adapter: str) -> LocalClient | None:
    endpoint = os.environ.get("CONTROLGUARD_MODEL_URL")
    if endpoint is None:
        return None
    model = os.environ.get(f"CONTROLGUARD_MODEL_{adapter.upper()}", os.environ.get("CONTROLGUARD_MODEL", ""))
    return LocalClient(endpoint, string(model, "local model name"))
