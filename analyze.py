"""Rebuild operational measurements and an offline reading comparison; no model calls."""
import html
import json
from pathlib import Path

from benchmark import EXPERIMENT, ROOT
from lite import digest, save, words


def totals(rows):
    usage = {name: sum(r["usage"].get(name, 0) for r in rows if r["usage"] is not None)
             for name in ("input_tokens", "cached_input_tokens", "output_tokens")}
    return {"calls": len(rows), "seconds": round(sum(r.get("seconds", 0) for r in rows), 3),
            "unknown_duration_calls": sum("seconds" not in r for r in rows),
            "unknown_usage_calls": sum(r["usage"] is None for r in rows), **usage,
            "uncached_input_tokens": usage["input_tokens"] - usage["cached_input_tokens"],
            "total_input_and_output_tokens": usage["input_tokens"] + usage["output_tokens"]}


def render(text):
    sections = []
    for paragraph in text.split("\n\n"):
        if paragraph.startswith("## "):
            sections.append("<h3>" + html.escape(paragraph[3:]) + "</h3>")
        elif paragraph.startswith("# "):
            sections.append("<h2>" + html.escape(paragraph[2:]) + "</h2>")
        elif paragraph.strip() in {"* * *", "---", "***"}:
            sections.append("<hr>")
        else:
            sections.append("<p>" + html.escape(paragraph).replace("\n", "<br>") + "</p>")
    return "\n".join(sections)


def main():
    baseline = json.loads((EXPERIMENT / "baseline-metadata.json").read_text(encoding="utf-8"))
    historical = [{"id": c["id"], "seconds": (c["wall_ms"] or 0) / 1000,
                   "usage": c["usage"][0] if len(c["usage"]) == 1 else None} for c in baseline["calls"]]
    manifest = json.loads((EXPERIMENT / "lite/run.json").read_text(encoding="utf-8"))
    if manifest["status"] != "complete":
        raise ValueError("Lite run is incomplete")
    for name, expected in manifest["artifacts"].items():
        if digest(EXPERIMENT / "lite" / name) != expected:
            raise ValueError(f"Lite artifact hash mismatch: {name}")
    receipts = [json.loads((EXPERIMENT / "lite" / p / "receipt.json").read_text(encoding="utf-8"))
                for p in manifest["attempts"]]
    heavy = (EXPERIMENT / "baseline/chapter-one.md").read_text(encoding="utf-8")
    light = (EXPERIMENT / "lite/chapter.md").read_text(encoding="utf-8")
    metrics = {"heavy_full": totals(historical),
               "heavy_chapter_stage": totals([r for r in historical if "chapter-" in r["id"]]),
               "lite": totals(receipts), "words": {"heavy": words(heavy), "lite": words(light)},
               "lite_runtime_source_lines": len((ROOT / "lite.py").read_text(encoding="utf-8").splitlines()),
               "notes": ["Times sum recorded model call durations; human checkpoint waits are excluded.",
                         "Historical draw 6 excludes earlier draws' costs.",
                         "Full heavyweight includes concept/listing/world work absent from Lite.",
                         "Evaluation calls are reported separately from generation.",
                         "Input includes cached input. Tokens are not dollars or subscription credits."]}
    evaluation = [json.loads(p.read_text(encoding="utf-8")) for p in
                  sorted((EXPERIMENT / "evaluation").glob("*/receipt.json"))]
    metrics["evaluation"] = totals(evaluation)
    save(EXPERIMENT / "metrics.json", metrics)
    # Artifacts on disk remain exact; this HTML is only an escaped reading presentation.
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opening chapter comparison · LitHarness Lite</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f8f5ef;color:#252822;font:17px/1.75 Georgia,serif}
header{padding:40px 5vw 24px;border-bottom:1px solid #d9d2c5}h1{font-size:clamp(28px,4vw,45px);line-height:1.15;margin:8px 0 18px}
.eyebrow,nav,.label,.stats{font:13px/1.6 system-ui,sans-serif;letter-spacing:.04em}
.eyebrow{color:#536552;text-transform:uppercase}header p{max-width:850px}a{color:#356044}
main{display:grid;grid-template-columns:1fr 1fr;gap:4vw;padding:30px 5vw 70px}article{min-width:0;max-width:760px}
article+article{border-left:1px solid #d9d2c5;padding-left:4vw}.label{position:sticky;top:0;background:#f8f5ef;padding:12px 0;border-bottom:2px solid #71846c;font-weight:700}
h2{font-size:29px;line-height:1.25;margin-top:30px}h3{font-size:20px}p{margin:0 0 1em}hr{width:40px;border:0;border-top:1px solid #aaa;margin:35px auto}
.stats{padding:14px 0;color:#536552}button{font:inherit;font-size:14px;background:#e4e9df;border:1px solid #899d83;border-radius:4px;padding:7px 14px;cursor:pointer}
body.single main{grid-template-columns:1fr}body.single article{max-width:760px;margin:auto}body.single article+article{border:0;padding:0}
@media(max-width:900px){main{display:block}article+article{border-left:0;border-top:2px solid #71846c;padding:35px 0;margin-top:50px}}
</style><header><div class="eyebrow">LitHarness Lite · One-brief pilot · 27 September 2026</div>
<h1>Two routes to an opening chapter</h1><p>Same original premise and model settings. One historical LitHarness chapter and one fresh two-call draft. This is a pilot, with different invented stories and substantial baseline history.</p>
<nav><a href="REPORT.md">Read the assessment</a> · <a href="PROTOCOL.md">Frozen method</a> · <a href="metrics.json">Measured costs</a></nav>
<p><button onclick="document.body.classList.toggle('single')">Toggle stacked reading</button></p></header><main>
"""
    for label, text, stat in (("LITHARNESS · HISTORICAL DRAW 6", heavy, metrics["heavy_full"]),
                             ("LITHARNESS LITE · FIRST DRAFT", light, metrics["lite"])):
        page += f'<article><div class="label">{label}</div><div class="stats">{words(text):,} words · {stat["calls"]} calls · {stat["seconds"]/60:.1f} minutes of model time</div>{render(text)}</article>'
    page += "</main></html>"
    (EXPERIMENT / "comparison.html").write_text(page, encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
