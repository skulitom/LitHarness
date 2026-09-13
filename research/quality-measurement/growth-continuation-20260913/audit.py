"""Read checkpoint databases and native receipts without changing the continuation."""

from __future__ import annotations

import hashlib
import json
import runpy
from collections import Counter
from pathlib import Path

RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, ROOT, RUN, BOOK, BASE, load, save, sha = (
    RUNNER[k] for k in ("HERE", "ROOT", "RUN", "BOOK", "BASE", "load", "save", "sha")
)


def stock_transition(before, after):
    system = before.system
    steps = system.rank_ids.index(after.rank_id) - system.rank_ids.index(before.rank_id)
    purchases = {
        a.ability_id: max(0, after.magnitude(a.ability_id) - before.magnitude(a.ability_id))
        for a in system.abilities
        if a.price
    }
    stocks = []
    for stock in system.abilities:
        if not stock.is_stock:
            continue
        cost = sum(
            purchases.get(a.ability_id, 0) * dict(a.price).get(stock.ability_id, 0)
            for a in system.abilities
        )
        earned = steps * stock.per_rung
        was, now = before.magnitude(stock.ability_id), after.magnitude(stock.ability_id)
        stocks.append(
            {
                "stock": stock.ability_id,
                "before": was,
                "after": now,
                "rank_grant": earned,
                "purchase_cost": cost,
                "balanced_under_seed_model": was + earned - cost == now,
            }
        )
    return {
        "same_system": system.digest == after.system.digest,
        "rank_steps": steps,
        "paid_capability_increases": purchases,
        "stocks": stocks,
    }


def main():
    progress = load(RUN / "progress.json")
    if progress["status"] == "running":
        raise RuntimeError("Wait until live work ends")
    manifest = load(RUN / "manifest.json")
    RUNNER["validate"](manifest)
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain import gamesystem as gs
    from litharness.domain import state

    calls, sessions = [], []
    for path in sorted((BOOK / "calls").glob("*.json")):
        row = load(path)
        raw = row.get("result", {}).get("raw", row.get("transport", {}))
        events, malformed = [], 0
        for line in raw.get("stdout", "").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                malformed += 1
        native = [e["thread_id"] for e in events if e.get("type") == "thread.started"]
        sessions.extend(native)
        tools = [
            e["item"]
            for e in events
            if e.get("type") == "item.completed"
            and e.get("item", {}).get("type") not in {"reasoning", "agent_message"}
        ]
        commands = [
            r
            for line in raw.get("commands_jsonl", "").splitlines()
            if (r := json.loads(line)).get("phase") == "result"
        ]
        counts = Counter(
            " ".join(c["arguments"][:2])
            if isinstance(c["arguments"], list)
            else "invalid tool request"
            for c in commands
        )
        calls.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "profile": row["request"]["profile"],
                "status": row["status"],
                "native_tokens": BASE.native_usage(raw),
                "sessions": native,
                "malformed_event_lines": malformed,
                "contained": all(
                    t.get("type") == "mcp_tool_call"
                    and t.get("server") == "litharness"
                    and t.get("tool") == "litharness_command"
                    for t in tools
                ),
                "verbatim": raw.get("mode") != "bridge"
                or raw.get("tool_reply_format") == "verbatim",
                "commands_by_verb": dict(counts),
                "failed_commands": [
                    {
                        "call": c["call"],
                        "returncode": c.get("returncode"),
                        "error_kind": c.get("error_kind"),
                    }
                    for c in commands
                    if c.get("error") or c.get("returncode") != 0
                ],
                "request_sha256": hashlib.sha256(
                    json.dumps(row["request"], sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
            }
        )
    initial = {r["record_id"]: r for r in load(BOOK / "initial-world.json")}
    previous_sheet = None
    previous_hashes = {}
    checkpoints = []
    for label in ["seeded", *(f"checkpoint-{n}" for n in range(1, RUNNER["CHAPTERS"] + 1))]:
        folder = BOOK / label
        if not folder.exists():
            continue
        database = folder / "serial.db"
        if not database.exists():
            checkpoints.append({"label": label, "complete": False})
            continue
        before_hash = sha(database)
        with SqliteStore.open_read_only(database) as store:
            [(book, branch, _)] = store.branches()
            records = [r for r in store.state_records(book, branch) if state.is_canon(r)]
        sheet = gs.sheet_of(records, "wren")
        hashes = load(folder / "chapter-hashes.json")
        shown = {r["record_id"]: r for r in load(folder / "world.json")["result"]}
        keys = ("subject", "predicate", "value", "object", "order_key", "says")
        retained = all(
            identity in shown
            and shown[identity]["canon"]
            and all(shown[identity].get(k) == row.get(k) for k in keys)
            for identity, row in initial.items()
        )
        check, verify = load(folder / "check.json"), load(folder / "verify.json")
        checkpoint = {
            "label": label,
            "complete": True,
            "database_sha256": before_hash,
            "database_unchanged": sha(database) == before_hash,
            "world_sha256": sha(folder / "world.json"),
            "check_sha256": sha(folder / "check.json"),
            "verify_sha256": sha(folder / "verify.json"),
            "check_ok": check["exit_code"] == 0 and check["result"]["ok"],
            "unplaceable": len(check["result"]["unplaceable"]),
            "attribution_ok": verify["exit_code"] == 0 and not verify["result"].get("unattributed"),
            "seed_records_retained_in_canon": retained,
            "chapter_hashes": hashes,
            "earlier_chapters_preserved": all(
                hashes.get(k) == v for k, v in previous_hashes.items()
            ),
            "sheet": None
            if sheet is None
            else {
                "system": sheet.system.system_id,
                "system_digest": sheet.system.digest,
                "rank": sheet.rank_id,
                "default_maximum": sheet.system.scale.maximum,
                "holdings": dict(sheet.magnitudes),
                "growth_limits": {a.ability_id: a.growth_limit for a in sheet.system.abilities},
            },
            "new_wants": [
                {
                    "record_id": r.record_id,
                    "subject": r.subject,
                    "order_key": state.order_key_of(r),
                    "value_sha256": hashlib.sha256(str(r.value).encode()).hexdigest(),
                }
                for r in records
                if r.predicate == "wants" and r.record_id not in initial
            ],
        }
        if previous_sheet is not None and sheet is not None:
            checkpoint["transition"] = stock_transition(previous_sheet, sheet)
        checkpoints.append(checkpoint)
        previous_sheet, previous_hashes = sheet, hashes
    native_tokens = sum(c["native_tokens"] or 0 for c in calls)
    by_profile = {}
    for call in calls:
        profile = by_profile.setdefault(call["profile"], {"calls": 0, "tokens": 0})
        profile["calls"] += 1
        profile["tokens"] += call["native_tokens"] or 0
    result = {
        "schema": "litharness.growth-continuation.v1",
        "status": progress["status"],
        "fatal": progress["fatal"],
        "manifest_sha256": sha(RUN / "manifest.json"),
        "progress_sha256": sha(RUN / "progress.json"),
        "calls": calls,
        "native_tokens": native_tokens,
        "usage_matches_progress": native_tokens == progress["tokens"],
        "session_count": len(sessions),
        "distinct_sessions": len(set(sessions)),
        "profiles": by_profile,
        "checkpoints": checkpoints,
        "protected_inputs_unchanged": all(
            sha(ROOT / p) == digest for p, digest in manifest["protected_inputs"].items()
        ),
    }
    save(HERE / "evidence.json", result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "fatal",
                    "native_tokens",
                    "profiles",
                    "usage_matches_progress",
                    "protected_inputs_unchanged",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
