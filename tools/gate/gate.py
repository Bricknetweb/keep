#!/usr/bin/env python3
"""Layer-improvement gate.

Read a PREREG markdown file and run its smoke command, then run1, then
run2. run2 starts only after run1 has exited and the exit code is 0.
Stdlib only. See README.md for the PREREG format.

Exit 0 on PASS, 1 on FAIL, 2 on a usage or PREREG format error.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import resource
except ImportError:  # Windows has no resource module
    resource = None

HELP = """\
usage: python3 gate.py PREREG.md

Read a PREREG markdown file and enforce the layer-improvement gate.
Exit 0 on PASS, 1 on FAIL, 2 on a usage or PREREG format error.
See README.md in this directory for the PREREG format.
"""

_FENCE = re.compile(r"^```prereg[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_ONCE = {"smoke", "run", "staging", "status", "md5sums", "memory_cap_mb"}
_MANY = {"script", "input", "output"}
_MD5 = re.compile(r"^[0-9a-f]{32}$")
_PHASES = ("smoke", "run1", "run2")


class ParseError(Exception):
    """The PREREG text is not in the gate format."""


@dataclass
class HashedFile:
    kind: str
    path: Path
    md5: str


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
    memory_cap_mb: int | None


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
    once: dict[str, str] = {}
    base = source.resolve(strict=False).parent
    seen_paths: set[Path] = set()
    seen_outputs: set[str] = set()

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
        check_output_name(value)
        if value in seen_outputs:
            raise ParseError(f"line {lineno}: duplicate output {value}")
        seen_outputs.add(value)
        outputs.append(value)

    missing = [name for name in ("smoke", "run", "staging", "status", "md5sums") if name not in once]
    if missing:
        raise ParseError("missing " + ", ".join(missing))
    if not scripts:
        raise ParseError("list at least one script")
    if not outputs:
        raise ParseError("list at least one output")
    split_command(once["smoke"])
    split_command(once["run"])

    cap: int | None = None
    if "memory_cap_mb" in once:
        raw_cap = once["memory_cap_mb"]
        if not raw_cap.isdigit() or int(raw_cap) < 1:
            raise ParseError("memory_cap_mb must be a positive integer")
        cap = int(raw_cap)

    staging = resolve_path(base, once["staging"])
    status = resolve_path(base, once["status"])
    md5sums = resolve_path(base, once["md5sums"])
    if len({staging, status, md5sums}) < 3:
        raise ParseError("staging, status, and md5sums must be three different paths")
    for phase in _PHASES:
        phase_dir = staging / phase
        if is_within(status, phase_dir) or is_within(md5sums, phase_dir):
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
        memory_cap_mb=cap,
    )


def memory_problem(phase: str, peak: int | None, cap_mb: int | None) -> str | None:
    """Return a FAIL reason when the optional cap is broken or unmeasured."""
    if cap_mb is None:
        return None
    if peak is None:
        return f"{phase}: memory cap {cap_mb} MiB set but peak RSS was unavailable"
    cap_bytes = cap_mb * 1024 * 1024
    if peak > cap_bytes:
        return f"{phase}: peak RSS {peak} bytes exceeds cap of {cap_mb} MiB ({cap_bytes} bytes)"
    return None


def verify_md5s(report: Report) -> str | None:
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


def sample_rss_bytes(pid: int) -> int | None:
    """Best-effort RSS sample. Failure here must not hide the command's exit code."""
    try:
        if sys.platform.startswith("linux"):
            return _linux_vmhwm(pid)
        if sys.platform == "darwin":
            return _darwin_rss(pid)
        if os.name == "nt":
            return _windows_peak_ws(pid)
    except Exception:
        return None
    return None


def _linux_vmhwm(pid: int) -> int | None:
    try:
        text = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("VmHWM:"):
            try:
                return int(line.split()[1]) * 1024
            except (IndexError, ValueError):
                return None
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


def _darwin_rss(pid: int) -> int | None:
    try:
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(pid)],
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = out.strip()
    if not text:
        return None
    return int(text.split()[0]) * 1024


def _windows_peak_ws(pid: int) -> int | None:
    import ctypes
    from ctypes import wintypes

    process_query = 0x1000
    process_vm_read = 0x0010
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    handle = kernel32.OpenProcess(process_query | process_vm_read, False, pid)
    if not handle:
        return None

    class ProcessMemoryCounters(ctypes.Structure):
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
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        size = int(counters.PeakWorkingSetSize)
        return size or None
    finally:
        kernel32.CloseHandle(handle)


def children_maxrss_bytes() -> int | None:
    if resource is None:
        return None
    try:
        rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    except (OSError, ValueError):
        return None
    if rss <= 0:
        return None
    if sys.platform == "darwin":
        return int(rss)
    return int(rss) * 1024


def _await_command(proc: subprocess.Popen[bytes], before: int | None) -> tuple[int, int | None, str]:
    """Wait for proc. Return its exit code, peak RSS in bytes, and where that came from.

    A single early sample is not the peak: resident set grows during startup.
    On Linux the loop keeps reading VmHWM until the process is a zombie, then reaps it.
    getrusage supplies the kernel high-water mark when this command sets a new one.
    """
    peak: int | None = None
    if sys.platform.startswith("linux"):
        while True:
            state = _linux_state(proc.pid)
            if state is None or state == "Z":
                break
            sample = _linux_vmhwm(proc.pid)
            if sample is not None:
                peak = sample if peak is None else max(peak, sample)
            time.sleep(0.002)
        code = proc.wait()
    else:
        while proc.poll() is None:
            sample = sample_rss_bytes(proc.pid)
            if sample is not None:
                peak = sample if peak is None else max(peak, sample)
            time.sleep(0.005)
        code = proc.returncode
        if code is None:
            code = proc.wait()
    after = children_maxrss_bytes()
    source = "sample" if peak is not None else "unavailable"
    if after is not None and (before is None or after > before):
        if peak is None or after > peak:
            peak = after
            source = "rusage"
    if peak is None:
        source = "unavailable"
    return code, peak, source


def launch(prereg: Prereg, phase: str, command: str) -> CommandRecord:
    """Run one command to completion. Does not start any other phase."""
    rec = CommandRecord(phase=phase, template=command)
    outdir = prereg.staging / phase
    rec.outdir = outdir
    if os.path.lexists(outdir):
        rec.note = f"{phase} output directory already exists: {outdir}"
        return rec
    try:
        outdir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        rec.note = f"{phase} output directory already exists: {outdir}"
        return rec
    except OSError as exc:
        rec.note = f"could not create {outdir}: {exc}"
        return rec
    for name in prereg.outputs:
        target = outdir / name
        if os.path.lexists(target):
            rec.note = f"refusing to overwrite {target}"
            return rec
    try:
        argv = expand_command(command, outdir, phase)
    except ParseError as exc:
        rec.note = str(exc)
        return rec
    rec.argv = argv
    env = os.environ.copy()
    env["GATE_PHASE"] = phase
    env["GATE_OUTDIR"] = str(outdir)
    rec.started = utc_now()
    t0 = time.monotonic()
    before = children_maxrss_bytes()
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(prereg.base),
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except OSError as exc:
        rec.finished = utc_now()
        rec.elapsed_sec = time.monotonic() - t0
        rec.note = f"could not start {phase}: {exc}"
        return rec
    rec.started_run = True
    code, peak, source = _await_command(proc, before)
    rec.exit_code = code
    rec.peak_rss_bytes = peak
    rec.peak_source = source
    rec.finished = utc_now()
    rec.elapsed_sec = time.monotonic() - t0
    return rec


def compare_outputs(report: Report) -> str | None:
    prereg = report.prereg
    for name in prereg.outputs:
        left = prereg.staging / "run1" / name
        right = prereg.staging / "run2" / name
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


def render_command(rec: CommandRecord | None, phase: str) -> list[str]:
    lines = [f"### {phase}", ""]
    if rec is None or not rec.started_run:
        note = rec.note if rec and rec.note else "not started"
        lines.append("- state: not started")
        lines.append(f"- note: {note}")
        lines.append("")
        return lines
    elapsed = f"{rec.elapsed_sec:.3f}" if rec.elapsed_sec is not None else "unavailable"
    lines.extend(
        [
            "- state: ran",
            f"- template: {rec.template}",
            f"- argv: {shlex.join(rec.argv or [])}",
            f"- outdir: {rec.outdir}",
            f"- exit_code: {rec.exit_code}",
            f"- started: {rec.started}",
            f"- finished: {rec.finished}",
            f"- elapsed_sec: {elapsed}",
            f"- peak_rss: {format_peak(rec)}",
            "",
        ]
    )
    return lines


def render_status(report: Report) -> str:
    prereg = report.prereg
    cap = "none" if prereg.memory_cap_mb is None else str(prereg.memory_cap_mb)
    lines = [
        "# STATUS",
        "",
        f"- verdict: {report.verdict}",
        f"- reason: {report.reason}",
        f"- prereg: {prereg.source}",
        f"- cwd: {prereg.base}",
        f"- started: {report.started}",
        f"- finished: {report.finished}",
        f"- memory_cap_mb: {cap}",
        "",
        "## Files",
        "",
    ]
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
    cap = "none" if prereg.memory_cap_mb is None else str(prereg.memory_cap_mb)
    lines = [
        f"# gate verdict: {report.verdict}",
        f"# reason: {report.reason}",
        f"# prereg: {prereg.source}",
        f"# cwd: {prereg.base}",
        f"# started: {report.started}",
        f"# finished: {report.finished}",
        f"# memory_cap_mb: {cap}",
    ]
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


def run_phase(report: Report, phase: str, command: str) -> str | None:
    rec = launch(report.prereg, phase, command)
    report.commands[phase] = rec
    if not rec.started_run:
        return rec.note or f"{phase} did not start"
    if rec.exit_code != 0:
        return f"{phase} exit code {rec.exit_code}"
    return memory_problem(phase, rec.peak_rss_bytes, report.prereg.memory_cap_mb)


def run_gate(prereg: Prereg) -> int:
    report = Report(prereg)
    if os.path.lexists(prereg.staging):
        report.blocked_root = prereg.staging
        return fail(report, f"staging already exists: {prereg.staging}")
    if os.path.lexists(prereg.status):
        return fail(report, f"refusing to overwrite {prereg.status}")
    if os.path.lexists(prereg.md5sums):
        return fail(report, f"refusing to overwrite {prereg.md5sums}")

    problem = verify_md5s(report)
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
