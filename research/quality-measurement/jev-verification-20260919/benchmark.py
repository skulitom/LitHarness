"""Frozen, local-only OpenJev classification screen. See RUNBOOK.md before running."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from jev_fixtures import LABELS, build_cases, digest, manifest  # noqa: E402

MODEL_REVISION = "4b5f9a67fa2ebe77466bce0656ce350effc3148c"
TEMPLATE = "Premise: {premise}\nHypothesis: {hypothesis}"
MAX_TOKENS = 4096
SEED = 20260919
CONFIDENCE = 0.9
REPO = HERE.parents[2]


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n",
    )


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def temperature() -> int:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    return int(result.stdout.strip().splitlines()[0])


def cool(elapsed: float) -> int:
    # RUNBOOK policy: one resting second per inference second; 72/66 C hysteresis.
    # Sensor failures raise and stop collection, rather than proceeding without a guard.
    time.sleep(elapsed)
    current = temperature()
    if current >= 72:
        while current >= 66:
            time.sleep(5)
            current = temperature()
    return current


def format_input(case: dict) -> str:
    return TEMPLATE.format(premise=case["premise"].strip(), hypothesis=case["hypothesis"].strip())


def check_tokens(lengths: list[int]) -> None:
    if not lengths or min(lengths) < 1 or max(lengths) > MAX_TOKENS:
        raise ValueError("Input outside registered token bound; never silently truncate")


def prediction(probabilities: list[float]) -> str:
    if (
        len(probabilities) != 3
        or any(not math.isfinite(p) or p < 0 or p > 1 for p in probabilities)
        or not math.isclose(sum(probabilities), 1.0, abs_tol=1e-5)
    ):
        raise ValueError("Invalid probability vector")
    return LABELS[max(range(3), key=lambda i: probabilities[i])]


def metrics(rows: list[dict]) -> dict:
    confusion = {gold: dict.fromkeys(LABELS, 0) for gold in LABELS}
    for row in rows:
        confusion[row["expected"]][row["prediction"]] += 1
    confident = [r for r in rows if max(r["probabilities"]) >= CONFIDENCE]
    mistakes = [r["id"] for r in rows if r["prediction"] != r["expected"]]
    return {
        "n": len(rows), "correct": len(rows) - len(mistakes),
        "accuracy": (len(rows) - len(mistakes)) / len(rows),
        "confusion_gold_then_prediction": confusion,
        "neutral_baseline_accuracy": sum(r["expected"] == "neutral" for r in rows) / len(rows),
        "confident_n": len(confident),
        "confident_errors": [r["id"] for r in confident if r["prediction"] != r["expected"]],
        "false_entailments": [
            r["id"] for r in rows
            if r["prediction"] == "entailment" and r["expected"] != "entailment"
        ],
        "confident_false_entailments": [
            r["id"] for r in confident
            if r["prediction"] == "entailment" and r["expected"] != "entailment"
        ],
        "multiclass_brier_sum": statistics.mean(
            sum((p - float(label == r["expected"])) ** 2
                for label, p in zip(LABELS, r["probabilities"], strict=True))
            for r in rows
        ),
        "mistakes": mistakes,
    }


def analyse(rows: list[dict], expected_manifest: dict) -> dict:
    expected = {r["id"]: r for r in expected_manifest["cases"]}
    if len(rows) != len(expected) or {r["id"] for r in rows} != set(expected):
        raise ValueError("Missing, duplicate or unexpected records; no complete result")
    for row in rows:
        if any(row.get(key) != value for key, value in expected[row["id"]].items()):
            raise ValueError("Result metadata does not match frozen case manifest")
        if prediction(row["probabilities"]) != row["prediction"]:
            raise ValueError("Stored prediction disagrees with probabilities")
    by_id = {r["id"]: r for r in rows}
    invariance = {}
    for variant in ("rename", "reflow", "distractor"):
        selected = [r for r in rows if r["variant"] == variant]
        flipped, shifts = [], []
        for row in selected:
            base = by_id[row["id"].rsplit(".", 1)[0] + ".base"]
            if row["prediction"] != base["prediction"]:
                flipped.append(row["id"])
            shifts.append(max(abs(a - b) for a, b in zip(
                row["probabilities"], base["probabilities"], strict=True)))
        invariance[variant] = {
            "n_pairs": len(selected), "prediction_flips": flipped,
            "mean_max_probability_shift": statistics.mean(shifts),
        }
    return {
        "dataset_sha256": expected_manifest["dataset_sha256"],
        "label_order": LABELS, "confidence_cutoff": CONFIDENCE,
        "all": metrics(rows),
        "by_variant": {
            v: metrics([r for r in rows if r["variant"] == v])
            for v in sorted({r["variant"] for r in rows})
        },
        "base_by_family": {
            f: metrics([r for r in rows if r["family"] == f and r["variant"] == "base"])
            for f in sorted({r["family"] for r in rows})
        },
        "base_by_surface": {
            str(s): metrics([r for r in rows if r["surface"] == s and r["variant"] == "base"])
            for s in (0, 1)
        },
        "invariance": invariance,
        "max_tokens": max(r["tokens"] for r in rows),
        "inference_seconds": sum(r["inference_seconds"] for r in rows),
        "max_observed_temperature_c": max(r["temperature_c"] for r in rows),
        "descriptive_only": True,
        "independent_books": 0,
    }


def verify_registration(model_dir: Path) -> dict:
    registration = json.loads((HERE / "registration.json").read_text(encoding="utf-8"))
    for relative, expected in registration["source_hashes"].items():
        if file_hash(REPO / relative) != expected:
            raise ValueError(f"Changed registered source: {relative}")
    if manifest() != json.loads((HERE / "manifest.json").read_text(encoding="utf-8")):
        raise ValueError("Dataset differs from registration")
    for relative, expected in registration["model_hashes"].items():
        if file_hash(model_dir / relative) != expected:
            raise ValueError(f"Changed model artifact: {relative}")
    for package, version in registration["packages"].items():
        if importlib.metadata.version(package) != version:
            raise ValueError(f"Changed runtime package: {package}")
    registered_paths = [
        *registration["source_hashes"], str(HERE.relative_to(REPO) / "registration.json")
    ]
    for relative in registered_paths:
        committed = subprocess.run(
            ["git", "show", f"HEAD:{Path(relative).as_posix()}"],
            cwd=REPO, check=True, capture_output=True,
        ).stdout
        if hashlib.sha256(committed).hexdigest() != file_hash(REPO / relative):
            raise ValueError(f"Registration is not committed: {relative}")
    return registration


def collect(model_dir: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("Output exists; preserve attempts, do not overwrite or silently resume")
    holder = (REPO / "runs/box.lock/holder").read_text(encoding="utf-8")
    if not holder.startswith("jev-verification-20260919:"):
        raise ValueError("This experiment does not hold the workstation lock")
    registration = verify_registration(model_dir)
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(4)
    torch.manual_seed(SEED)
    if not torch.cuda.is_available():
        raise RuntimeError("Registered CUDA device unavailable")
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir, local_files_only=True, trust_remote_code=False,
    )
    tokenizer.padding_side = "right"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    cases = build_cases()
    random.Random(SEED).shuffle(cases)
    lengths = [len(tokenizer(format_input(case), truncation=False)["input_ids"]) for case in cases]
    check_tokens(lengths)
    cool(0)
    started = time.monotonic()
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, local_files_only=True, trust_remote_code=False, dtype=torch.bfloat16,
        attn_implementation="eager",
    ).to("cuda").eval()
    if model.config.nli_template != TEMPLATE or model.config.id2label != dict(enumerate(LABELS)):
        raise ValueError("Model template or label order differs from registration")
    model.config.get_text_config().pad_token_id = tokenizer.pad_token_id
    backbone = getattr(model, model.base_model_prefix)
    output.parent.mkdir(parents=True, exist_ok=True)
    wall_start = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        for index, (case, tokens) in enumerate(zip(cases, lengths, strict=True)):
            if time.monotonic() - started >= 45 * 60:
                raise RuntimeError("Registered 45 minute ceiling reached")
            cool(0)
            encoded = tokenizer(
                format_input(case), truncation=False, return_tensors="pt",
            ).to("cuda")
            torch.cuda.synchronize()
            tick = time.monotonic()
            with torch.inference_mode():
                hidden = backbone(**encoded, use_cache=False).last_hidden_state
                last = encoded["attention_mask"].sum(1) - 1
                pooled = hidden[torch.arange(hidden.size(0), device="cuda"), last]
                probabilities = model.score(pooled).float().softmax(-1)[0].cpu().tolist()
            torch.cuda.synchronize()
            elapsed = time.monotonic() - tick
            current = temperature()
            row = {
                key: value for key, value in case.items() if key not in {"premise", "hypothesis"}
            }
            row.update({
                "probabilities": probabilities, "prediction": prediction(probabilities),
                "tokens": tokens, "inference_seconds": elapsed, "temperature_c": current,
            })
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
            del hidden, pooled, encoded
            cool(elapsed)
            if (index + 1) % 12 == 0:
                print(f"{index + 1}/{len(cases)} pairs; GPU {current} C", flush=True)
    write_json(output.with_suffix(".runtime.json"), {
        "model_revision": MODEL_REVISION, "registration_sha256": digest(registration),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
        ).strip(),
        "device": torch.cuda.get_device_name(0), "dtype": "bfloat16", "attention": "eager",
        "batch_size": 1, "pairs": len(cases),
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "collection_wall_seconds": time.monotonic() - wall_start,
        "including_load_seconds": time.monotonic() - started,
        "api_calls": 0, "hosted_jev_measured": False,
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("manifest")
    run = sub.add_parser("run")
    run.add_argument("--model-dir", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    report = sub.add_parser("analyse")
    report.add_argument("--raw", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "manifest":
        write_json(HERE / "manifest.json", manifest())
    elif args.action == "run":
        collect(args.model_dir, args.output)
    else:
        rows = [json.loads(line) for line in args.raw.read_text(encoding="utf-8").splitlines()]
        expected = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
        result = analyse(rows, expected)
        result["raw_sha256"] = file_hash(args.raw)
        write_json(args.output, result)


if __name__ == "__main__":
    main()
