"""Byte-exact atomic writes, hashes, and locks that are cleared only when their holder provably ended."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time

HOLDER = re.compile(r"^litharness pid=(\d+) start=(\S+) ")


class Held(Exception):
    """A lock that another process holds, or that this runtime cannot prove abandoned."""


def home() -> Path:
    return Path(os.environ.get("LITHARNESS_HOME") or Path.home() / "LitHarness-data")


def utc() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return sha(Path(path).read_bytes())


def read(path: Path) -> str:
    return Path(path).read_bytes().decode("utf-8")


def write(path: Path, value: str | bytes) -> str:
    """Temp file, fsync, os.replace; returns the sha256 of the bytes stored, which never gain a CR."""
    path, data = Path(path), value.encode("utf-8") if isinstance(value, str) else value
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(8):
        try:
            os.replace(temporary, path)
            return sha(data)
        except PermissionError:  # Windows: a reader or scanner holds the target for a moment
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))
    raise AssertionError("unreachable")


def save(path: Path, value: object) -> str:
    return write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load(path: Path) -> dict:
    return json.loads(read(path))


def probe(pid: int) -> tuple[bool, str]:
    """(provably ended, creation-time token or '-'). os.kill(pid, 0) would terminate it on Windows."""
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return False, Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        except ProcessLookupError:
            return True, "-"
        except (PermissionError, OSError, IndexError):
            return False, "-"
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ctypes.get_last_error() == 87, "-"  # ERROR_INVALID_PARAMETER: no such process
    try:
        code, times = wintypes.DWORD(), [wintypes.FILETIME() for _ in range(4)]
        ended = kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259  # STILL_ACTIVE
        known = kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times))
        return bool(ended), str(times[0].dwHighDateTime << 32 | times[0].dwLowDateTime) if known else "-"
    finally:
        kernel.CloseHandle(handle)


def gone(pid: int, start: str) -> bool:
    """True only when the holder provably ended, or its PID now belongs to a later process."""
    ended, now = probe(pid)
    return ended or ("-" not in (now, start) and now != start)


def lock(directory: Path, label: str) -> None:
    """mkdir is the atomic step. A holder in our own form whose process is gone is cleared once."""
    directory.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            directory.mkdir()
        except FileExistsError:
            holder = directory / "holder"
            line = read(holder).strip() if holder.is_file() else ""
            match = HOLDER.match(line)
            if not (match and gone(int(match[1]), match[2])):
                raise Held(line or f"{directory} (no holder line)") from None
            holder.unlink(missing_ok=True)
            directory.rmdir()
            continue
        write(directory / "holder", f"litharness pid={os.getpid()} start={probe(os.getpid())[1]} {label} {utc()}\n")
        return
    raise Held(f"{directory} (could not be taken)")


def unlock(directory: Path) -> None:
    holder = directory / "holder"
    match = HOLDER.match(read(holder)) if holder.is_file() else None
    if match and int(match[1]) == os.getpid():
        holder.unlink()
        directory.rmdir()


def box_lock(start: Path | None = None) -> Path:
    """runs/box.lock in the main checkout, found from the .git entry above the package without git."""
    for parent in Path(start or __file__).resolve().parents:
        entry = parent / ".git"
        if entry.is_dir():
            return parent / "runs" / "box.lock"
        if entry.is_file():  # a worktree: its gitdir names the common directory inside the main checkout
            gitdir = Path(read(entry).split("gitdir:", 1)[1].strip())
            gitdir = gitdir if gitdir.is_absolute() else (parent / gitdir).resolve()
            common = gitdir / "commondir"
            common_dir = (gitdir / read(common).strip()).resolve() if common.is_file() else gitdir
            return common_dir.parent / "runs" / "box.lock"
    return home() / "box.lock"
