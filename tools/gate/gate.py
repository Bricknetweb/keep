#!/usr/bin/env python3
"""Layer-improvement gate.

Read a PREREG markdown file and run its smoke command, then run1, then
run2. run2 starts only after run1 has exited and the exit code is 0.
The gate does not create the step output directory; {outdir} is
staging/<phase>/out and the step creates it.

Stdlib only. See README.md for the PREREG format.

Exit 0 on PASS, 1 on FAIL, 2 on a usage or PREREG format error.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HELP = """\
usage: python3 gate.py PREREG.md

Read a PREREG markdown file and enforce the layer-improvement gate.
Exit 0 on PASS, 1 on FAIL, 2 on a usage or PREREG format error.
See README.md in this directory for the PREREG format.
"""

_FENCE = re.compile(r"^```prereg[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_PREREG_MD5_LINE = re.compile(br"^prereg_md5:[ \t]*([0-9a-fA-F]{32})[ \t]*\r?\n?$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ONCE = {
    "smoke",
    "run",
    "staging",
    "status",
    "md5sums",
    "prereg_md5",
    "memory_cap_mb",
    "free_ram_floor_mb",
    "timeout_sec",
    "smoke_timeout_sec",
    "run_timeout_sec",
}
_MANY = {"script", "input", "output", "env", "smoke_env", "run_env"}
_MD5 = re.compile(r"^[0-9a-f]{32}$")
_PHASES = ("smoke", "run1", "run2")
_OUT_NAME = "out"
_POLL_SEC = 0.01


class ParseError(Exception):
    """The PREREG text is not in the gate format."""


@dataclass
class HashedFile:
    kind: str
    path: Path
    md5: str


@dataclass
class PreregMd5:
    declared: str
    actual: str


@dataclass
class Prereg:
    source: Path
    base: Path
    files: list[HashedFile]
    smoke: str
    run: str
    outputs: list[str]
    staging: Path
    status: Path
    md5sums: Path
    declared_md5: str
    env: list[tuple[str, str]]
    smoke_env: list[tuple[str, str]]
    run_env: list[tuple[str, str]]
    memory_cap_mb: int | None
    free_ram_floor_mb: int | None
    timeout_sec: int | None
    smoke_timeout_sec: int | None
    run_timeout_sec: int | None


@dataclass
class StepLimits:
    cap_bytes: int | None
    cap_mb: int | None
    floor_bytes: int | None
    floor_mb: int | None
    timeout_sec: int | None


@dataclass
class CommandRecord:
    phase: str
    template: str
    argv: list[str] | None = None
    outdir: Path | None = None
    exit_code: int | None = None
    started: str = ""
    finished: str = ""
    elapsed_sec: float | None = None
    peak_rss_bytes: int | None = None
    peak_source: str = "unavailable"
    started_run: bool = False
    note: str = ""
    failure: str = ""
    stdout_log: str = ""
    stderr_log: str = ""
    env_md5: str = ""


@dataclass
class Report:
    prereg: Prereg
    verdict: str = "FAIL"
    reason: str = ""
    started: str = ""
    finished: str = ""
    blocked_root: Path | None = None
    file_lines: list[str] = field(default_factory=list)
    md5_lines: list[str] = field(default_factory=list)
    output_lines: list[str] = field(default_factory=list)
    commands: dict[str, CommandRecord] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.started:
            self.started = utc_now()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def is_within(path: Path, root: Path) -> bool:
    path = path.resolve(strict=False)
    root = root.resolve(strict=False)
    if path == root:
        return True
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def resolve_path(base: Path, text: str) -> Path:
    raw = Path(text)
    if not raw.is_absolute():
        raw = base / raw
    return raw.resolve(strict=False)


def phase_dir(prereg: Prereg, phase: str) -> Path:
    return prereg.staging / phase


def output_dir(prereg: Prereg, phase: str) -> Path:
    """Directory the step must create. The gate does not create it."""
    return phase_dir(prereg, phase) / _OUT_NAME


def split_command(command: str) -> list[str]:
    posix = os.name != "nt"
    try:
        parts = shlex.split(command, posix=posix)
    except ValueError as exc:
        raise ParseError(f"could not parse command: {exc}") from exc
    if not parts:
        raise ParseError("command is empty")
    if not any("{outdir}" in part for part in parts):
        raise ParseError("command must include {outdir} so outputs stay in staging")
    return parts


def expand_command(command: str, outdir: Path, phase: str) -> list[str]:
    argv = []
    for part in split_command(command):
        part = part.replace("{outdir}", str(outdir))
        part = part.replace("{phase}", phase)
        argv.append(part)
    return argv


def check_output_name(name: str) -> None:
    if not name or any(ch in name for ch in "\\:"):
        raise ParseError(f"bad output name {name!r}")
    path = Path(name)
    if path.is_absolute() or path.drive:
        raise ParseError(f"output must be a relative file name, got {name!r}")
    if any(part in (".", "..") for part in path.parts):
        raise ParseError(f"output must stay inside the run directory, got {name!r}")


def _one_line(text: str) -> str:
    return " ".join(text.split())


def parse_env_assignment(text: str, lineno: int) -> tuple[str, str]:
    name, sep, value = text.partition("=")
    if not sep:
        raise ParseError(f"line {lineno}: env needs NAME=VALUE")
    if not _ENV_NAME.match(name) or "\x00" in value:
        raise ParseError(f"line {lineno}: bad environment assignment {text!r}")
    return name, value


def parse_positive_int(text: str, key: str) -> int:
    if not text.isdigit() or int(text) < 1:
        raise ParseError(f"{key} must be a positive integer")
    return int(text)


def read_prereg_md5(path: Path) -> PreregMd5:
    """Hash the file with its single column-0 prereg_md5 line removed."""
    data = path.read_bytes()
    declared: str | None = None
    kept: list[bytes] = []
    for line in data.splitlines(keepends=True):
        match = _PREREG_MD5_LINE.match(line)
        if match is None:
            kept.append(line)
            continue
        if declared is not None:
            raise ParseError("more than one prereg_md5 line")
        declared = match.group(1).decode("ascii").lower()
    if declared is None:
        raise ParseError("missing prereg_md5")
    return PreregMd5(declared, md5_bytes(b"".join(kept)))


def env_canonical(pairs: list[tuple[str, str]]) -> bytes:
    return "".join(f"{name}={value}\n" for name, value in pairs).encode("utf-8")


def env_md5(pairs: list[tuple[str, str]]) -> str:
    return md5_bytes(env_canonical(pairs))


def merge_env(base: list[tuple[str, str]], override: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Apply override on top of base. Override keys stay in their first position."""
    values = dict(base)
    order = [name for name, _value in base]
    for name, value in override:
        if name not in values:
            order.append(name)
        values[name] = value
    return [(name, values[name]) for name in order]


def step_env(prereg: Prereg, phase: str) -> list[tuple[str, str]]:
    extra = prereg.smoke_env if phase == "smoke" else prereg.run_env
    return merge_env(prereg.env, extra)


def timeout_for(prereg: Prereg, phase: str) -> int | None:
    if phase == "smoke" and prereg.smoke_timeout_sec is not None:
        return prereg.smoke_timeout_sec
    if phase != "smoke" and prereg.run_timeout_sec is not None:
        return prereg.run_timeout_sec
    return prereg.timeout_sec


def limits_for(prereg: Prereg, phase: str) -> StepLimits:
    cap = prereg.memory_cap_mb
    floor = prereg.free_ram_floor_mb
    return StepLimits(
        cap_bytes=None if cap is None else cap * 1024 * 1024,
        cap_mb=cap,
        floor_bytes=None if floor is None else floor * 1024 * 1024,
        floor_mb=floor,
        timeout_sec=timeout_for(prereg, phase),
    )


def parse_prereg(text: str, source: Path) -> Prereg:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(_FENCE.finditer(text))
    if not matches:
        raise ParseError("no ```prereg fenced block found")
    if len(matches) > 1:
        raise ParseError("more than one ```prereg block")
    scripts: list[HashedFile] = []
    inputs: list[HashedFile] = []
    outputs: list[str] = []
    env: list[tuple[str, str]] = []
    smoke_env: list[tuple[str, str]] = []
    run_env: list[tuple[str, str]] = []
    once: dict[str, str] = {}
    base = source.resolve(strict=False).parent
    seen_paths: set[Path] = set()
    seen_outputs: set[str] = set()
    seen_env: dict[str, set[str]] = {"env": set(), "smoke_env": set(), "run_env": set()}

    for lineno, raw in enumerate(matches[0].group(1).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ParseError(f"line {lineno}: expected key: value")
        key = key.strip().lower()
        value = value.strip()
        if key not in _ONCE and key not in _MANY:
            raise ParseError(f"line {lineno}: unknown key {key!r}")
        if not value:
            raise ParseError(f"line {lineno}: {key} has no value")
        if key == "prereg_md5" and not raw.startswith("prereg_md5:"):
            raise ParseError(f"line {lineno}: prereg_md5 must start at column 0")
        if key in _ONCE:
            if key in once:
                raise ParseError(f"line {lineno}: {key} is already set")
            once[key] = value
            continue
        if key in ("script", "input"):
            tokens = value.split()
            if len(tokens) != 2:
                raise ParseError(
                    f"line {lineno}: {key} needs '<path> <md5>' with no spaces in the path"
                )
            path_text, digest = tokens
            digest = digest.lower()
            if not _MD5.match(digest):
                raise ParseError(f"line {lineno}: md5 must be 32 hex characters")
            path = resolve_path(base, path_text)
            if path in seen_paths:
                raise ParseError(f"line {lineno}: duplicate path {path}")
            seen_paths.add(path)
            item = HashedFile(key, path, digest)
            if key == "script":
                scripts.append(item)
            else:
                inputs.append(item)
            continue
        if key in ("env", "smoke_env", "run_env"):
            name, env_value = parse_env_assignment(value, lineno)
            if name in seen_env[key]:
                raise ParseError(f"line {lineno}: duplicate {key} name {name}")
            seen_env[key].add(name)
            bucket = {"env": env, "smoke_env": smoke_env, "run_env": run_env}[key]
            bucket.append((name, env_value))
            continue
        check_output_name(value)
        if value in seen_outputs:
            raise ParseError(f"line {lineno}: duplicate output {value}")
        seen_outputs.add(value)
        outputs.append(value)

    missing = [
        name
        for name in ("smoke", "run", "staging", "status", "md5sums", "prereg_md5")
        if name not in once
    ]
    if missing:
        raise ParseError("missing " + ", ".join(missing))
    if not scripts:
        raise ParseError("list at least one script")
    if not outputs:
        raise ParseError("list at least one output")
    declared = once["prereg_md5"].lower()
    if not _MD5.match(declared):
        raise ParseError("prereg_md5 must be 32 hex characters")
    split_command(once["smoke"])
    split_command(once["run"])

    integers: dict[str, int | None] = {}
    for name in (
        "memory_cap_mb",
        "free_ram_floor_mb",
        "timeout_sec",
        "smoke_timeout_sec",
        "run_timeout_sec",
    ):
        integers[name] = None if name not in once else parse_positive_int(once[name], name)

    staging = resolve_path(base, once["staging"])
    status = resolve_path(base, once["status"])
    md5sums = resolve_path(base, once["md5sums"])
    if len({staging, status, md5sums}) < 3:
        raise ParseError("staging, status, and md5sums must be three different paths")
    for phase in _PHASES:
        folder = staging / phase
        if is_within(status, folder) or is_within(md5sums, folder):
            raise ParseError("status and md5sums must not sit inside smoke, run1, or run2")

    return Prereg(
        source=source.resolve(strict=False),
        base=base,
        files=scripts + inputs,
        smoke=once["smoke"],
        run=once["run"],
        outputs=outputs,
        staging=staging,
        status=status,
        md5sums=md5sums,
        declared_md5=declared,
        env=env,
        smoke_env=smoke_env,
        run_env=run_env,
        memory_cap_mb=integers["memory_cap_mb"],
        free_ram_floor_mb=integers["free_ram_floor_mb"],
        timeout_sec=integers["timeout_sec"],
        smoke_timeout_sec=integers["smoke_timeout_sec"],
        run_timeout_sec=integers["run_timeout_sec"],
    )


def memory_problem(phase: str, peak: int | None, cap_mb: int | None) -> str | None:
    """Return a FAIL reason when the optional cap is broken or unmeasured."""
    if cap_mb is None:
        return None
    if peak is None:
        return f"{phase}: memory cap {cap_mb} MiB set but process-tree RSS was unavailable"
    cap_bytes = cap_mb * 1024 * 1024
    if peak > cap_bytes:
        return (
            f"{phase}: process-tree RSS {peak} bytes exceeds cap of "
            f"{cap_mb} MiB ({cap_bytes} bytes)"
        )
    return None


def first_file_problem(files: list[HashedFile]) -> str | None:
    for item in files:
        if not _regular(item.path):
            return f"missing {item.kind} {item.path}"
        actual = md5_file(item.path)
        if actual != item.md5:
            return f"md5 mismatch for {item.path}: expected {item.md5} actual {actual}"
    return None


def record_file_checks(report: Report) -> str | None:
    """Record script and input hashes. Stop at the first problem."""
    for item in report.prereg.files:
        if not _regular(item.path):
            report.file_lines.append(f"- {item.kind} {item.path} MISSING")
            return f"missing {item.kind} {item.path}"
        actual = md5_file(item.path)
        report.md5_lines.append(f"{actual}  {item.path}")
        if actual != item.md5:
            report.file_lines.append(
                f"- {item.kind} {item.path} expected {item.md5} actual {actual} MISMATCH"
            )
            report.md5_lines.append(
                f"# mismatch {item.path} expected {item.md5} actual {actual}"
            )
            return f"md5 mismatch for {item.path}"
        report.file_lines.append(f"- {item.kind} {item.path} md5 {actual} ok")
    return None


def free_ram_bytes() -> int | None:
    """Best-effort available RAM. None when this OS cannot report it."""
    try:
        if sys.platform.startswith("linux"):
            return _linux_memavailable()
        if sys.platform == "darwin":
            return _darwin_free_ram()
        if os.name == "nt":
            return _windows_avail_phys()
    except Exception:
        return None
    return None


def _linux_memavailable() -> int | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return None


def _darwin_free_ram() -> int | None:
    try:
        out = subprocess.check_output(["vm_stat"], text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    page = 4096
    counts: dict[str, int] = {}
    for line in out.splitlines():
        if "page size of" in line:
            for token in line.replace("(", " ").replace(")", " ").split():
                if token.isdigit():
                    page = int(token)
                    break
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        number = value.strip().strip(".").replace(".", "")
        if number.isdigit():
            counts[label.strip()] = int(number)
    pages = 0
    found = False
    for label in ("Pages free", "Pages inactive", "Pages speculative"):
        if label in counts:
            pages += counts[label]
            found = True
    if not found:
        return None
    return pages * page


def _windows_avail_phys() -> int | None:
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullAvailPhys) or None


def tree_rss_bytes(pid: int) -> int | None:
    """Current RSS of pid plus descendants. None when it cannot be read."""
    try:
        if sys.platform.startswith("linux"):
            return _linux_tree_rss(pid)
        if sys.platform == "darwin":
            return _darwin_tree_rss(pid)
        if os.name == "nt":
            return _windows_tree_rss(pid)
    except Exception:
        return None
    return None


def _linux_status_kb(pid: int, label: str) -> int | None:
    try:
        text = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        return None
    prefix = label + ":"
    for line in text.splitlines():
        if line.startswith(prefix):
            try:
                return int(line.split()[1]) * 1024
            except (IndexError, ValueError):
                return None
    return None


def _linux_ppid(pid: int) -> int | None:
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    mark = text.rfind(")")
    if mark < 0:
        return None
    fields = text[mark + 2 :].split()
    if len(fields) < 2:
        return None
    try:
        return int(fields[1])
    except ValueError:
        return None


def _linux_state(pid: int) -> str | None:
    """Process state from /proc, or None when the pid is already gone."""
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    mark = text.rfind(")")
    if mark < 0 or mark + 2 >= len(text):
        return None
    return text[mark + 2]


def _linux_tree_rss(root: int) -> int | None:
    children: dict[int, list[int]] = {}
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        ppid = _linux_ppid(pid)
        if ppid is None:
            continue
        children.setdefault(ppid, []).append(pid)
    total = 0
    found = False
    stack = [root]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        rss = _linux_status_kb(pid, "VmRSS")
        if rss is not None:
            found = True
            total += rss
        stack.extend(children.get(pid, ()))
    return total if found else None


def _darwin_tree_rss(root: int) -> int | None:
    try:
        out = subprocess.check_output(
            ["ps", "-ax", "-o", "pid=,ppid=,rss="],
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    rss: dict[int, int] = {}
    children: dict[int, list[int]] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            pid, ppid, rss_kb = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        rss[pid] = rss_kb * 1024
        children.setdefault(ppid, []).append(pid)
    total = 0
    found = False
    stack = [root]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if pid in rss:
            found = True
            total += rss[pid]
        stack.extend(children.get(pid, ()))
    return total if found else None


def _windows_tree_rss(root: int) -> int | None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value or snapshot == -1:
        return None

    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    children: dict[int, list[int]] = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Process32First(snapshot, ctypes.byref(entry)):
            return None
        while True:
            children.setdefault(int(entry.th32ParentProcessID), []).append(int(entry.th32ProcessID))
            if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)

    total = 0
    found = False
    stack = [root]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        rss = _windows_working_set(pid)
        if rss is not None:
            found = True
            total += rss
        stack.extend(children.get(pid, ()))
    return total if found else None


def _windows_working_set(pid: int) -> int | None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        return None

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    try:
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return int(counters.WorkingSetSize) or None
    finally:
        kernel32.CloseHandle(handle)


def kill_tree(proc: subprocess.Popen[bytes]) -> None:
    """Kill proc and descendants. The POSIX child is its own process group."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass


def _await_command(
    proc: subprocess.Popen[bytes],
    phase: str,
    limits: StepLimits,
    started_at: float,
) -> tuple[int, int | None, str, str]:
    """Poll until proc exits. Kill the tree on cap, free-RAM floor, or timeout."""
    peak: int | None = None
    failure = ""
    while True:
        rss = tree_rss_bytes(proc.pid)
        if rss is not None:
            peak = rss if peak is None else max(peak, rss)
        if limits.cap_bytes is not None and rss is not None and rss > limits.cap_bytes:
            failure = (
                f"{phase}: killed, process-tree RSS {rss} bytes exceeds cap of "
                f"{limits.cap_mb} MiB ({limits.cap_bytes} bytes)"
            )
            kill_tree(proc)
            break
        if limits.floor_bytes is not None:
            free = free_ram_bytes()
            if free is not None and free < limits.floor_bytes:
                failure = (
                    f"{phase}: killed, free RAM {free} bytes below floor of "
                    f"{limits.floor_mb} MiB ({limits.floor_bytes} bytes)"
                )
                kill_tree(proc)
                break
        if limits.timeout_sec is not None and (time.monotonic() - started_at) >= limits.timeout_sec:
            failure = f"{phase}: killed, timeout {limits.timeout_sec}s"
            kill_tree(proc)
            break
        if proc.poll() is not None:
            break
        time.sleep(_POLL_SEC)
    try:
        code = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        code = proc.wait(timeout=5)
    source = "tree" if peak is not None else "unavailable"
    if limits.cap_bytes is not None and peak is None and not failure:
        failure = f"{phase}: memory cap {limits.cap_mb} MiB set but process-tree RSS was unavailable"
    return code, peak, source, failure


def floor_blocks(limits: StepLimits, phase: str) -> str | None:
    if limits.floor_bytes is None:
        return None
    free = free_ram_bytes()
    if free is None:
        return f"{phase}: free RAM floor set but free RAM was unavailable"
    if free < limits.floor_bytes:
        return (
            f"{phase}: free RAM {free} bytes below floor of "
            f"{limits.floor_mb} MiB ({limits.floor_bytes} bytes)"
        )
    return None


def launch(prereg: Prereg, phase: str, command: str) -> CommandRecord:
    """Run one command to completion. Does not start any other phase.

    Creates the phase directory for new stdout and stderr logs only.
    Does not create {outdir} (the `out` directory); the step does that.
    """
    rec = CommandRecord(phase=phase, template=command, env_md5=env_md5(step_env(prereg, phase)))
    folder = phase_dir(prereg, phase)
    out_dir = output_dir(prereg, phase)
    rec.outdir = out_dir
    if os.path.lexists(folder):
        rec.note = f"{phase} directory already exists: {folder}"
        return rec
    if os.path.lexists(out_dir):
        rec.note = f"refusing to overwrite {out_dir}"
        return rec
    limits = limits_for(prereg, phase)
    blocked = floor_blocks(limits, phase)
    if blocked:
        rec.note = blocked
        rec.failure = blocked
        return rec
    try:
        folder.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        rec.note = f"{phase} directory already exists: {folder}"
        return rec
    except OSError as exc:
        rec.note = f"could not create {folder}: {exc}"
        return rec
    if os.path.lexists(out_dir):
        rec.note = f"refusing to overwrite {out_dir}"
        return rec
    stdout_path = folder / "stdout.log"
    stderr_path = folder / "stderr.log"
    rec.stdout_log = str(stdout_path)
    rec.stderr_log = str(stderr_path)
    stdout_fh = None
    stderr_fh = None
    try:
        stdout_fh = stdout_path.open("xb")
        stderr_fh = stderr_path.open("xb")
    except OSError as exc:
        if stdout_fh is not None:
            stdout_fh.close()
        if isinstance(exc, FileExistsError):
            which = stdout_path if stdout_fh is None else stderr_path
            rec.note = f"refusing to overwrite {which}"
        else:
            rec.note = f"could not create log: {exc}"
        return rec
    try:
        argv = expand_command(command, out_dir, phase)
    except ParseError as exc:
        rec.note = str(exc)
        stdout_fh.close()
        stderr_fh.close()
        return rec
    rec.argv = argv
    env = os.environ.copy()
    for name, value in step_env(prereg, phase):
        env[name] = value
    env["GATE_PHASE"] = phase
    env["GATE_OUTDIR"] = str(out_dir)
    env["PYTHONUNBUFFERED"] = "1"
    rec.started = utc_now()
    t0 = time.monotonic()
    popen_kwargs: dict[str, object] = {
        "cwd": str(prereg.base),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": stdout_fh,
        "stderr": stderr_fh,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(argv, **popen_kwargs)
    except OSError as exc:
        rec.finished = utc_now()
        rec.elapsed_sec = time.monotonic() - t0
        rec.note = f"could not start {phase}: {exc}"
        return rec
    finally:
        stdout_fh.close()
        stderr_fh.close()
    rec.started_run = True
    code, peak, source, failure = _await_command(proc, phase, limits, t0)
    rec.exit_code = code
    rec.peak_rss_bytes = peak
    rec.peak_source = source
    rec.failure = failure
    rec.finished = utc_now()
    rec.elapsed_sec = time.monotonic() - t0
    return rec


def compare_outputs(report: Report) -> str | None:
    prereg = report.prereg
    for name in prereg.outputs:
        left = output_dir(prereg, "run1") / name
        right = output_dir(prereg, "run2") / name
        if not _regular(left):
            report.output_lines.append(f"- {name} run1 missing")
            return f"run1 missing output {name}"
        if not _regular(right):
            digest = md5_file(left)
            report.md5_lines.append(f"{digest}  {left}")
            report.output_lines.append(f"- {name} run1 {digest} run2 missing")
            return f"run2 missing output {name}"
        first = md5_file(left)
        second = md5_file(right)
        report.md5_lines.append(f"{first}  {left}")
        report.md5_lines.append(f"{second}  {right}")
        if first != second:
            report.output_lines.append(f"- {name} run1 {first} run2 {second} differ")
            return f"output md5 mismatch for {name}"
        report.output_lines.append(f"- {name} run1 {first} run2 {second} match")
    return None


def format_peak(rec: CommandRecord) -> str:
    if rec.peak_rss_bytes is None:
        return "unavailable"
    mib = rec.peak_rss_bytes / (1024 * 1024)
    return f"{mib:.1f} MiB ({rec.peak_rss_bytes} bytes, {rec.peak_source})"


def render_environment(prereg: Prereg) -> list[str]:
    lines = ["## Environment", ""]
    for label, phase in (("smoke", "smoke"), ("run", "run1")):
        pairs = step_env(prereg, phase)
        lines.append(f"- {label} env_md5: {env_md5(pairs)}")
        if pairs:
            for name, value in pairs:
                lines.append(f"- {label} env: {name}={value}")
        else:
            lines.append(f"- {label} env: (none)")
        timeout = timeout_for(prereg, phase)
        lines.append(f"- {label} timeout_sec: {'none' if timeout is None else timeout}")
    lines.append("")
    return lines


def render_command(rec: CommandRecord | None, phase: str) -> list[str]:
    lines = [f"### {phase}", ""]
    if rec is None or not rec.started_run:
        note = rec.note if rec and rec.note else "not started"
        lines.append("- state: not started")
        lines.append(f"- note: {note}")
        if rec and rec.env_md5:
            lines.append(f"- env_md5: {rec.env_md5}")
        lines.append("")
        return lines
    elapsed = f"{rec.elapsed_sec:.3f}" if rec.elapsed_sec is not None else "unavailable"
    lines.extend(
        [
            "- state: ran",
            f"- template: {rec.template}",
            f"- argv: {shlex.join(rec.argv or [])}",
            f"- outdir: {rec.outdir}",
            f"- env_md5: {rec.env_md5}",
            f"- stdout_log: {rec.stdout_log}",
            f"- stderr_log: {rec.stderr_log}",
            f"- exit_code: {rec.exit_code}",
            f"- started: {rec.started}",
            f"- finished: {rec.finished}",
            f"- elapsed_sec: {elapsed}",
            f"- peak_rss: {format_peak(rec)}",
        ]
    )
    if rec.failure:
        lines.append(f"- failure: {rec.failure}")
    lines.append("")
    return lines


def render_status(report: Report) -> str:
    prereg = report.prereg
    lines = [
        "# STATUS",
        "",
        f"- verdict: {report.verdict}",
        f"- reason: {report.reason}",
        f"- prereg: {prereg.source}",
        f"- prereg_md5: {prereg.declared_md5}",
        f"- cwd: {prereg.base}",
        f"- started: {report.started}",
        f"- finished: {report.finished}",
        f"- memory_cap_mb: {'none' if prereg.memory_cap_mb is None else prereg.memory_cap_mb}",
        f"- free_ram_floor_mb: {'none' if prereg.free_ram_floor_mb is None else prereg.free_ram_floor_mb}",
        f"- timeout_sec: {'none' if prereg.timeout_sec is None else prereg.timeout_sec}",
        f"- smoke_timeout_sec: {'none' if prereg.smoke_timeout_sec is None else prereg.smoke_timeout_sec}",
        f"- run_timeout_sec: {'none' if prereg.run_timeout_sec is None else prereg.run_timeout_sec}",
        "",
    ]
    lines.extend(render_environment(prereg))
    lines.extend(["## Files", ""])
    lines.extend(report.file_lines or ["- not checked"])
    lines.extend(["", "## Commands", ""])
    for phase in _PHASES:
        lines.extend(render_command(report.commands.get(phase), phase))
    lines.extend(["## Outputs", ""])
    lines.extend(report.output_lines or ["- not compared"])
    lines.append("")
    return "\n".join(lines)


def render_md5sums(report: Report) -> str:
    prereg = report.prereg
    lines = [
        f"# gate verdict: {report.verdict}",
        f"# reason: {report.reason}",
        f"# prereg: {prereg.source}",
        f"# prereg_md5: {prereg.declared_md5}",
        f"# cwd: {prereg.base}",
        f"# started: {report.started}",
        f"# finished: {report.finished}",
        f"# memory_cap_mb: {'none' if prereg.memory_cap_mb is None else prereg.memory_cap_mb}",
        f"# free_ram_floor_mb: {'none' if prereg.free_ram_floor_mb is None else prereg.free_ram_floor_mb}",
        f"# timeout_sec: {'none' if prereg.timeout_sec is None else prereg.timeout_sec}",
        f"# smoke_timeout_sec: {'none' if prereg.smoke_timeout_sec is None else prereg.smoke_timeout_sec}",
        f"# run_timeout_sec: {'none' if prereg.run_timeout_sec is None else prereg.run_timeout_sec}",
    ]
    for label, phase in (("smoke", "smoke"), ("run", "run1")):
        pairs = step_env(prereg, phase)
        digest = env_md5(pairs)
        lines.append(f"# {label} env_md5: {digest}")
        for name, value in pairs:
            lines.append(f"# {label} env: {name}={value}")
        lines.append(f"{digest}  env:{label}")
    for phase in _PHASES:
        rec = report.commands.get(phase)
        if rec is None or not rec.started_run:
            lines.append(f"# {phase}: not started")
            continue
        lines.append(f"# {phase} command: {shlex.join(rec.argv or [])}")
        lines.append(f"# {phase} exit: {rec.exit_code}")
        lines.append(f"# {phase} started: {rec.started}")
        lines.append(f"# {phase} finished: {rec.finished}")
        elapsed = f"{rec.elapsed_sec:.3f}" if rec.elapsed_sec is not None else "unavailable"
        lines.append(f"# {phase} elapsed_sec: {elapsed}")
        lines.append(f"# {phase} peak_rss: {format_peak(rec)}")
        lines.append(f"# {phase} stdout_log: {rec.stdout_log}")
        lines.append(f"# {phase} stderr_log: {rec.stderr_log}")
        if rec.failure:
            lines.append(f"# {phase} failure: {rec.failure}")
    lines.extend(report.md5_lines)
    lines.append("")
    return "\n".join(lines)


def write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_records(report: Report) -> list[str]:
    errors = []
    blocked = report.blocked_root
    pairs = (
        (report.prereg.status, render_status(report)),
        (report.prereg.md5sums, render_md5sums(report)),
    )
    for path, text in pairs:
        if os.path.lexists(path):
            errors.append(f"refusing to overwrite {path}")
            continue
        if blocked is not None and is_within(path, blocked):
            errors.append(f"refusing to write inside existing staging: {path}")
            continue
        try:
            write_new(path, text)
        except FileExistsError:
            errors.append(f"refusing to overwrite {path}")
        except OSError as exc:
            errors.append(f"could not write {path}: {exc}")
    return errors


def finish(report: Report, code: int) -> int:
    report.finished = utc_now()
    report.reason = _one_line(report.reason)
    errors = write_records(report)
    sys.stdout.write(f"{report.verdict}: {report.reason}\n")
    for err in errors:
        sys.stderr.write(err + "\n")
    if errors:
        return 1
    return code


def fail(report: Report, reason: str) -> int:
    report.verdict = "FAIL"
    report.reason = reason
    return finish(report, 1)


def recheck_before(report: Report, phase: str) -> str | None:
    """Re-read the PREREG, scripts, and inputs immediately before a step."""
    try:
        info = read_prereg_md5(report.prereg.source)
    except (ParseError, OSError) as exc:
        message = f"before {phase}: prereg {exc}"
        report.file_lines.append(f"- recheck {message}")
        return message
    if info.declared != info.actual:
        message = (
            f"before {phase}: prereg md5 mismatch expected {info.declared} actual {info.actual}"
        )
        report.file_lines.append(f"- recheck {message}")
        return message
    problem = first_file_problem(report.prereg.files)
    if problem:
        message = f"before {phase}: {problem}"
        report.file_lines.append(f"- recheck {message}")
        return message
    report.file_lines.append(f"- recheck before {phase}: ok")
    return None


def run_phase(report: Report, phase: str, command: str) -> str | None:
    problem = recheck_before(report, phase)
    if problem:
        report.commands[phase] = CommandRecord(
            phase=phase,
            template=command,
            note=problem,
            env_md5=env_md5(step_env(report.prereg, phase)),
        )
        return problem
    rec = launch(report.prereg, phase, command)
    report.commands[phase] = rec
    if not rec.started_run:
        return rec.failure or rec.note or f"{phase} did not start"
    if rec.failure:
        return rec.failure
    if rec.exit_code != 0:
        return f"{phase} exit code {rec.exit_code}"
    return memory_problem(phase, rec.peak_rss_bytes, report.prereg.memory_cap_mb)


def check_prereg_hash(report: Report) -> str | None:
    try:
        info = read_prereg_md5(report.prereg.source)
    except (ParseError, OSError) as exc:
        return f"prereg {exc}"
    report.md5_lines.append(f"{info.actual}  {report.prereg.source}")
    if info.declared != info.actual or info.declared != report.prereg.declared_md5:
        report.file_lines.append(
            f"- prereg {report.prereg.source} expected {info.declared} actual {info.actual} MISMATCH"
        )
        return f"prereg md5 mismatch for {report.prereg.source}"
    report.file_lines.append(f"- prereg {report.prereg.source} md5 {info.actual} ok")
    return None


def run_gate(prereg: Prereg) -> int:
    report = Report(prereg)
    if os.path.lexists(prereg.staging):
        report.blocked_root = prereg.staging
        return fail(report, f"staging already exists: {prereg.staging}")
    if os.path.lexists(prereg.status):
        return fail(report, f"refusing to overwrite {prereg.status}")
    if os.path.lexists(prereg.md5sums):
        return fail(report, f"refusing to overwrite {prereg.md5sums}")

    problem = check_prereg_hash(report)
    if problem:
        return fail(report, problem)
    problem = record_file_checks(report)
    if problem:
        return fail(report, problem)

    problem = run_phase(report, "smoke", prereg.smoke)
    if problem:
        return fail(report, problem)
    problem = run_phase(report, "run1", prereg.run)
    if problem:
        return fail(report, problem)
    # run1 has been waited on and its exit code is 0. run2 starts only now.
    problem = run_phase(report, "run2", prereg.run)
    if problem:
        return fail(report, problem)

    problem = compare_outputs(report)
    if problem:
        return fail(report, problem)
    report.verdict = "PASS"
    report.reason = "smoke, run1, and run2 agreed"
    return finish(report, 0)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return 0
    if len(argv) != 1:
        sys.stderr.write(HELP)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        sys.stderr.write(f"not a file: {path}\n")
        return 2
    try:
        prereg = parse_prereg(path.read_text(encoding="utf-8-sig"), path)
    except ParseError as exc:
        sys.stderr.write(f"PREREG: {exc}\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"PREREG: {exc}\n")
        return 2
    return run_gate(prereg)


if __name__ == "__main__":
    sys.exit(main())
