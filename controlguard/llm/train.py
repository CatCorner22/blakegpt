import argparse
from decimal import Decimal
from importlib import import_module
import json
import os
from pathlib import Path
from typing import Any

from controlguard.inputs import Fields, decode, encode, fields, finite, integer, items, string

from .evaluate import load_rows, measure
from .model import ModelSpec, verify_snapshot
from .tools import ADAPTERS


def prompt_for(tokenizer: Any, row: Fields) -> str:
    messages = items(row["messages"], "messages")[:2]
    prompt = tokenizer.apply_chat_template(messages, tools=row["tools"], tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
    if not isinstance(prompt, str):
        raise ValueError("The tokenizer did not return a text prompt.")
    return prompt


def json_native(value: object) -> object:
    if isinstance(value, Decimal):
        return finite(value)
    if isinstance(value, dict):
        return {key: json_native(child) for key, child in fields(value).items()}
    if isinstance(value, list):
        return [json_native(child) for child in items(value, "value")]
    return value


def completion_for(row: Fields) -> str:
    expected = fields(row["expected"])
    call = json.dumps({"name": expected["name"], "arguments": json_native(expected["arguments"])},
                      allow_nan=False, ensure_ascii=True, separators=(",", ":"))
    return f"<tool_call>\n{call}\n</tool_call><|im_end|>"


def predictions(model: Any, tokenizer: Any, torch: Any, rows: list[Fields]) -> list[str]:
    model.eval()
    result: list[str] = []
    with torch.inference_mode():
        for row in rows:
            tokens = tokenizer(prompt_for(tokenizer, row), return_tensors="pt",
                               add_special_tokens=False).to(model.device)
            end = model.generate(**tokens, max_new_tokens=180, do_sample=False, temperature=1.0, top_p=1.0,
                                 top_k=50, use_cache=True)
            result.append(str(tokenizer.decode(end[0, tokens.input_ids.shape[1]:], skip_special_tokens=True)))
    return result


def train(config: Fields, data: Path, output: Path) -> None:
    adapter = string(config.get("adapter"), "adapter")
    if adapter not in ADAPTERS:
        raise ValueError("Use adapter a1 or a2.")
    spec = ModelSpec(string(config.get("repo"), "repo"), string(config.get("revision"), "revision"))
    spec.validate()
    mode = string(config.get("mode"), "mode")
    if mode not in {"cpu-lora", "gpu-qlora"}:
        raise ValueError("Use cpu-lora or gpu-qlora.")
    steps = integer(config.get("steps"), "steps", range(1, 100_001))
    eval_limit = integer(config.get("eval_limit", 4), "eval_limit", range(1, 513))
    hubs = import_module("huggingface_hub")
    torch = import_module("torch")
    transformers = import_module("transformers")
    trl = import_module("trl")
    peft = import_module("peft")
    datasets = import_module("datasets")
    cpu = mode == "cpu-lora"
    if not cpu and not torch.cuda.is_available():
        raise ValueError("GPU QLoRA needs a CUDA device.")
    if cpu:
        torch.set_num_threads(min(8, os.cpu_count() or 1))
    snapshot = Path(hubs.snapshot_download(repo_id=spec.repo, revision=spec.revision,
                                          allow_patterns=["*.safetensors", "*.json", "*.txt"]))
    verify_snapshot(snapshot)
    tokenizer = transformers.AutoTokenizer.from_pretrained(str(snapshot), trust_remote_code=False,
                                                          local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    options: dict[str, Any] = {"trust_remote_code": False, "use_safetensors": True, "local_files_only": True,
                               "dtype": torch.float32 if cpu else torch.bfloat16}
    if not cpu:
        options.update(device_map={"": 0}, quantization_config=transformers.BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16))
    model = transformers.AutoModelForCausalLM.from_pretrained(str(snapshot), **options)
    if not cpu:
        model = peft.prepare_model_for_kbit_training(model)
    training = load_rows(data / f"{adapter}-train.jsonl")
    heldout = load_rows(data / f"{adapter}-eval.jsonl")[:eval_limit]
    if not training or not heldout:
        raise ValueError("Generate nonempty training and held-out files.")
    output.mkdir(parents=True, exist_ok=True)
    before = predictions(model, tokenizer, torch, heldout)
    print(encode({"before": measure(heldout, before)}), flush=True)
    dataset = datasets.Dataset.from_list([{"prompt": prompt_for(tokenizer, row),
                                           "completion": completion_for(row)} for row in training])
    lora = peft.LoraConfig(r=8 if cpu else 32, lora_alpha=16 if cpu else 64,
                           target_modules=["q_proj", "v_proj"] if cpu else "all-linear", task_type="CAUSAL_LM")
    params = trl.SFTConfig(
        output_dir=str(output / "trainer"), max_steps=steps, per_device_train_batch_size=1,
        gradient_accumulation_steps=1 if cpu else 8, completion_only_loss=True,
        learning_rate=3e-4 if cpu else 1e-4, logging_steps=1 if cpu else 10,
        max_length=2048, save_strategy="no", report_to="none", use_cpu=cpu, bf16=not cpu,
        gradient_checkpointing=not cpu, lr_scheduler_type="constant", seed=42,
    )
    trainer = trl.SFTTrainer(model=model, args=params, train_dataset=dataset, peft_config=lora,
                             processing_class=tokenizer)
    trainer.train()
    trainer.model.save_pretrained(str(output / "adapter"), safe_serialization=True)
    tokenizer.save_pretrained(str(output / "adapter"))
    after = predictions(trainer.model, tokenizer, torch, heldout)
    for tag, values in (("before", before), ("after", after)):
        (output / f"{tag}.jsonl").write_text(
            "".join(encode({"prediction": value}) + "\n" for value in values), encoding="utf-8")
    metrics = {"before": measure(heldout, before), "after": measure(heldout, after)}
    (output / "metrics.json").write_text(encode(metrics, pretty=True) + "\n", encoding="utf-8")
    print(encode(metrics), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate a pinned ControlGuard adapter.")
    parser.add_argument("config", type=Path)
    parser.add_argument("--data", type=Path, default=Path("llm-output/data"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    train(decode(args.config.read_text(encoding="utf-8")), args.data, args.output)


if __name__ == "__main__":
    main()
