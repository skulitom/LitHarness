"""An independent watchdog for GPU runs on this box. Runs beside a job, not inside it.

**Why a second process.** `force_gpu.Governor` throttles between calls, which is the right place
for a duty cycle and the wrong place for a safety cut-out: a governor that lives inside the job
cannot act while the job is *in* a call, and a 512-token batched generation is forty seconds of
uninterruptible work. On 2026-08-20 this box went down mid-run with a core temperature that never
exceeded 65 C in any sample the run logged — so the in-process governor's own record was the
thing that could not see it coming.

This samples every `--interval` seconds regardless of what the job is doing, writes a CSV trace
that survives the job, and **kills the job** when a hard limit is crossed. A run that dies to this
watchdog leaves its checkpoint intact and resumes for free; a run that dies to a power cut leaves
whatever the filesystem had.

**The thresholds are stops, not targets.** The soft one holds; the hard one kills. They sit below
the card's own limits on purpose: the card protecting itself is already a failure of ours.

    uv run python research/quality-measurement/thermal_watch.py --log results/thermal-<run>.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

#: Kill the job above this core temperature. Below the 72 C the inherited governor paused at, and
#: well below the ~74 C this card reports as its own throttle point.
HARD_CORE_C = 70

#: Kill if the card reports it is throttling itself for this many consecutive samples. One sample
#: is a transient; a run of them is the card doing our job for us.
HARD_THROTTLE_SAMPLES = 6

#: Kill if the margin to the card's own thermal limit falls to this. `temperature.gpu.tlimit`
#: reports degrees remaining, so small is bad — the opposite direction to every other reading
#: here, which is exactly the sort of sign error §89's rulebook keeps cataloguing.
#:
#: **Trips on this sensor must PERSIST, and that correction cost two killed runs.** The first
#: reading of the trace said `tlimit` tracks the die hotspot and is therefore the binding sensor
#: the core governor was missing. A longer trace refuses that:
#:
#:     t = 201 s   core 58 C   margin 19 C   power 296 W
#:     t = 211 s   core 53 C   margin  6 C   power  93 W
#:
#: The margin fell 13 C while the core fell 5 C and the draw fell 200 W. Nothing thermal moves
#: that way, so these are **transient dips** — the same shape appeared at t=50 s and recovered to
#: 21 C on the next sample — and killing on a single one is a false positive that ends healthy
#: runs. What this module is entitled to say is narrower than the first draft claimed: core
#: temperature and power draw are interpretable, `tlimit` is not, and an uninterpreted sensor may
#: contribute to a kill only when it says the same thing several samples running.
HARD_TLIMIT_MARGIN_C = 6

#: Consecutive low-margin samples required before the margin may kill anything.
HARD_MARGIN_SAMPLES = 3

FIELDS = (
    "temperature.gpu",
    "temperature.gpu.tlimit",
    "power.draw",
    "utilization.gpu",
    "memory.used",
    "clocks_event_reasons.hw_thermal_slowdown",
    "clocks_event_reasons.sw_thermal_slowdown",
    "clocks_event_reasons.hw_power_brake_slowdown",
)


def sample() -> dict[str, str]:
    out = subprocess.run(
        ["nvidia-smi", f"--query-gpu={','.join(FIELDS)}", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=False,
    ).stdout.strip()
    if not out:
        return {}
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    return dict(zip(FIELDS, parts, strict=False))


def as_float(value: str | None) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def gpu_python_pids(only_pattern: str = "") -> list[int]:
    """PIDs of python processes holding GPU memory, optionally filtered by command line.

    **`only_pattern` is not optional in practice, and the reason is that this box is shared.**
    Parallel sessions run GPU jobs on the same card (house rule), and on 2026-08-20 one of them
    started an F3 job while this watchdog was armed for a different run. An unfiltered watchdog
    would have SIGTERMed another session's work on the next thermal trip — destroying hours of
    someone else's compute to protect a card that was never in danger from it. Always pass the
    module name of the job you are actually guarding.
    """
    out = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=10, check=False,
    ).stdout.strip()
    pids: list[int] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and "python" in parts[1].lower():
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            if only_pattern and not _cmdline_matches(pid, only_pattern):
                continue
            pids.append(pid)
    return pids


def _cmdline_matches(pid: int, pattern: str) -> bool:
    out = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f"(Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\").CommandLine",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=20, check=False,
    ).stdout
    return pattern.lower() in (out or "").lower()


def kill(pids: list[int], reason: str) -> None:
    print(f"WATCHDOG KILL: {reason}; terminating {pids}", flush=True)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError) as error:
            print(f"  pid {pid}: {type(error).__name__}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--log", default=str(HERE / "results" / "thermal-watch.csv"))
    parser.add_argument("--hard-core", type=float, default=HARD_CORE_C)
    parser.add_argument("--hard-margin", type=float, default=HARD_TLIMIT_MARGIN_C)
    parser.add_argument("--max-minutes", type=float, default=0.0, help="0 = until killed")
    parser.add_argument("--only", default="",
                        help="only terminate GPU processes whose command line contains "
                             "this (e.g. the module name). REQUIRED on a shared box: "
                             "parallel sessions run their own GPU jobs on this card.")
    parser.add_argument("--no-kill", action="store_true", help="observe only")
    args = parser.parse_args(argv)

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    throttled_streak = 0
    margin_streak = 0
    peak_core = 0.0
    peak_power = 0.0
    min_margin = 999.0

    with log_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["elapsed_s", *FIELDS])
        while True:
            row = sample()
            if row:
                elapsed = round(time.time() - started, 1)
                writer.writerow([elapsed, *[row.get(f, "") for f in FIELDS]])
                handle.flush()

                core = as_float(row.get("temperature.gpu"))
                power = as_float(row.get("power.draw"))
                margin = as_float(row.get("temperature.gpu.tlimit"))
                throttling = any(
                    (row.get(f) or "").lower() in ("active", "true")
                    for f in FIELDS
                    if "slowdown" in f
                )
                if core is not None:
                    peak_core = max(peak_core, core)
                if power is not None:
                    peak_power = max(peak_power, power)
                if margin is not None:
                    min_margin = min(min_margin, margin)
                throttled_streak = throttled_streak + 1 if throttling else 0
                low_margin = margin is not None and margin <= args.hard_margin
                margin_streak = margin_streak + 1 if low_margin else 0

                trip = None
                if core is not None and core >= args.hard_core:
                    trip = f"core {core}C >= {args.hard_core}C"
                elif margin_streak >= HARD_MARGIN_SAMPLES:
                    trip = (
                        f"tlimit margin <= {args.hard_margin}C for {margin_streak} "
                        "consecutive samples"
                    )
                elif throttled_streak >= HARD_THROTTLE_SAMPLES:
                    trip = f"card throttling for {throttled_streak} consecutive samples"
                if trip and not args.no_kill:
                    pids = gpu_python_pids(args.only)
                    if pids:
                        kill(pids, trip)
                        print(
                            f"peaks: core {peak_core}C power {peak_power}W "
                            f"min margin {min_margin}C",
                            flush=True,
                        )
                        return 1

            if args.max_minutes and (time.time() - started) / 60 >= args.max_minutes:
                break
            time.sleep(args.interval)

    print(
        f"watchdog clean: peak core {peak_core}C, peak power {peak_power}W, "
        f"min tlimit margin {min_margin}C, log {log_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
