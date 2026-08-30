"""RUNBOOK free leg 3 as a script: build `fictions-v0.json`, the excerpt pass's artifact.

Reads the registered pairing (`pairs-v0.json`), pulls the denormalised rows for PAIRED
fiction ids only from the twelve cached RoyalRoad shards, and writes
`{fiction_id: [row, ...]}` with chapter text carried — exactly the shape
`backtest.load_fictions` reads. Runs under the MirrorBench venv (the only interpreter with
pyarrow); deterministic given the pinned snapshot; no model call, no network.

    C:/DEV/MirrorBench/.venv/Scripts/python.exe research/sim-readership-backtest/excerpt_pass.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = (
    Path.home()
    / ".cache/huggingface/hub/datasets--OmniAICreator--RoyalRoad-1.61M/snapshots"
    / "0e4df3f22999a7b7fa13b1e7564a09b5f3eb964e/data"
)
SHARDS = [1, 2, 3, 4, 5, 6, 28, 29, 30, 31, 32, 33]


def main() -> None:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    payload = json.loads((HERE / "pairs-v0.json").read_text(encoding="utf-8"))
    wanted: set[str] = set()
    for entry in payload["pairs"]:
        wanted.add(str(entry["high"]))
        wanted.add(str(entry["low"]))
    print(f"{len(payload['pairs'])} pairs -> {len(wanted)} fiction ids")

    grouped: dict[str, list[dict]] = {}
    for shard in SHARDS:
        path = SNAPSHOT / f"train-{shard:05d}-of-00047.parquet"
        table = pq.read_table(path)
        ids = table.column("fiction_id").cast("string")
        mask = pc.is_in(ids, value_set=__import__("pyarrow").array(sorted(wanted)))
        hit = table.filter(mask)
        for row in hit.to_pylist():
            grouped.setdefault(str(row.get("fiction_id")), []).append(row)
        print(f"shard {shard}: {hit.num_rows} rows ({len(grouped)} fictions so far)")

    missing = wanted - set(grouped)
    if missing:
        print(f"WARNING: {len(missing)} paired ids with no rows: {sorted(missing)[:5]}...")
    out = HERE / "fictions-v0.json"
    out.write_text(json.dumps(grouped, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(grouped)} fictions)")


if __name__ == "__main__":
    main()
