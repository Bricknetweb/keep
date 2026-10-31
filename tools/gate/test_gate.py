"""Unit tests for the layer-improvement gate.

Run from the repo root:

    python3 tools/gate/test_gate.py
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import re
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate


PASS_SCRIPT = """\
import sys
from pathlib import Path

phase, outdir, infile, log = sys.argv[1:5]
outdir_path = Path(outdir)
existed = int(outdir_path.exists())
with Path(log).open("a", encoding="utf-8") as handle:
    handle.write(phase + " " + outdir_path.name + " existed=" + str(existed) + "\\n")
if existed:
    raise SystemExit(2)
outdir_path.mkdir()
data = Path(infile).read_bytes()
(outdir_path / "mesh.obj").write_bytes(b"solid\\n" + data)
"""

RUN1_FAIL_SCRIPT = """\
import sys
from pathlib import Path

phase, outdir, log = sys.argv[1:4]
outdir_path = Path(outdir)
with Path(log).open("a", encoding="utf-8") as handle:
    handle.write(phase + "\\n")
if outdir_path.exists():
    raise SystemExit(2)
outdir_path.mkdir()
if phase == "run1":
    raise SystemExit(1)
(outdir_path / "mesh.obj").write_bytes(b"solid\\n")
"""

NONDET_SCRIPT = """\
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
if outdir.exists():
    raise SystemExit(2)
outdir.mkdir()
(outdir / "mesh.obj").write_text(str(outdir.resolve()) + "\\n", encoding="utf-8")
"""

MARKER_SCRIPT = """\
import sys
from pathlib import Path

Path(sys.argv[2]).write_text("ran\\n", encoding="utf-8")
"""

MUTATE_SCRIPT = """\
import sys
from pathlib import Path

phase, outdir, infile = sys.argv[1:4]
outdir_path = Path(outdir)
if outdir_path.exists():
    raise SystemExit(2)
outdir_path.mkdir()
data = Path(infile).read_bytes()
(outdir_path / "mesh.obj").write_bytes(b"solid\\n" + data)
if phase == "smoke":
    with Path(infile).open("ab") as handle:
        handle.write(b"\\nchanged\\n")
"""

ENV_SCRIPT = """\
import os
import sys
from pathlib import Path

phase, outdir = sys.argv[1:3]
outdir_path = Path(outdir)
if outdir_path.exists():
    raise SystemExit(2)
outdir_path.mkdir()
text = " ".join([
    os.environ.get("OMP_NUM_THREADS", ""),
    os.environ.get("MKL_NUM_THREADS", ""),
    os.environ.get("OPENBLAS_NUM_THREADS", ""),
    os.environ.get("LAYER_STEP", ""),
]) + "\\n"
(outdir_path / "mesh.obj").write_text(text, encoding="utf-8")
sys.stdout.write("stdout " + phase + "\\n")
sys.stderr.write("stderr " + phase + "\\n")
"""

SLEEP_SCRIPT = """\
import sys
import time
from pathlib import Path

phase, outdir, flag = sys.argv[1:4]
Path(flag).write_text("started\\n", encoding="utf-8")
outdir_path = Path(outdir)
if not outdir_path.exists():
    outdir_path.mkdir()
(outdir_path / "mesh.obj").write_bytes(b"mesh\\n")
time.sleep(10)
Path(flag).write_text("started\\ndone\\n", encoding="utf-8")
"""

TREE_PARENT = """\
import subprocess
import sys
import time
from pathlib import Path

phase, outdir, child, pidfile = sys.argv[1:5]
outdir_path = Path(outdir)
if outdir_path.exists():
    raise SystemExit(2)
outdir_path.mkdir()
(outdir_path / "mesh.obj").write_bytes(b"mesh\\n")
proc = subprocess.Popen([sys.executable, child])
Path(pidfile).write_text(str(proc.pid), encoding="utf-8")
time.sleep(10)
"""

TREE_CHILD = """\
import time
blob = bytearray(160 * 1024 * 1024)
for index in range(0, len(blob), 4096):
    blob[index] = 1
time.sleep(10)
"""


class LayerGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_gate(self, prereg: Path) -> int:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = gate.main([str(prereg)])
        self.gate_out = stdout.getvalue()
        self.gate_err = stderr.getvalue()
        return code

    def write_prereg(self, body: str, name: str = "PREREG.md") -> Path:
        path = self.root / name
        text = "# test prereg\n\n```prereg\n" + body.strip() + "\n```\n"
        payload = text.encode("utf-8")
        digest = hashlib.md5(payload).hexdigest()
        line = f"prereg_md5: {digest}\n".encode("utf-8")
        updated = payload.replace(b"```prereg\n", b"```prereg\n" + line, 1)
        path.write_bytes(updated)
        info = gate.read_prereg_md5(path)
        if info.declared != info.actual:
            raise AssertionError(f"prereg helper mismatch {info.declared} != {info.actual}")
        return path

    def command(self, script: Path, args: list[str]) -> str:
        parts = [sys.executable, str(script), *args]
        for part in parts:
            if any(ch.isspace() for ch in part):
                self.fail(f"test path has whitespace and would split: {part}")
        return " ".join(parts)

    def mesh(self, phase: str) -> Path:
        return self.root / "stage" / phase / "out" / "mesh.obj"

    def status_text(self) -> str:
        return (self.root / "STATUS.md").read_text(encoding="utf-8")

    def smoke_elapsed(self, status: str) -> float:
        match = re.search(r"### smoke\n\n(?:.*\n)*?- elapsed_sec: ([0-9.]+)", status)
        if match is None:
            self.fail(f"no smoke elapsed line in {status}")
        return float(match.group(1))

    def test_pass(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(PASS_SCRIPT, encoding="utf-8")
        synthetic = self.root / "synthetic.txt"
        sample = self.root / "sample.txt"
        synthetic.write_text("synthetic\n", encoding="utf-8")
        sample.write_text("sample\n", encoding="utf-8")
        log = self.root / "phases.log"
        smoke = self.command(script, ["{phase}", "{outdir}", str(synthetic), str(log)])
        run = self.command(script, ["{phase}", "{outdir}", str(sample), str(log)])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"input: synthetic.txt {gate.md5_file(synthetic)}",
                    f"input: sample.txt {gate.md5_file(sample)}",
                    f"smoke: {smoke}",
                    f"run: {run}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 0)
        self.assertTrue(self.gate_out.startswith("PASS:"))
        self.assertEqual(
            log.read_text(encoding="utf-8"),
            "smoke out existed=0\nrun1 out existed=0\nrun2 out existed=0\n",
        )
        smoke_mesh = self.mesh("smoke").read_bytes()
        run1_mesh = self.mesh("run1").read_bytes()
        run2_mesh = self.mesh("run2").read_bytes()
        self.assertEqual(smoke_mesh, b"solid\n" + synthetic.read_bytes())
        self.assertEqual(run1_mesh, b"solid\n" + sample.read_bytes())
        self.assertEqual(run2_mesh, run1_mesh)
        status = self.status_text()
        md5sums = (self.root / "MD5SUMS").read_text(encoding="utf-8")
        self.assertIn("- verdict: PASS", status)
        self.assertEqual(status.count("elapsed_sec:"), 3)
        self.assertEqual(status.count("exit_code:"), 3)
        self.assertEqual(status.count("peak_rss:"), 3)
        self.assertIn("match", status)
        self.assertIn("- recheck before smoke: ok", status)
        self.assertIn("- recheck before run1: ok", status)
        self.assertIn("- recheck before run2: ok", status)
        self.assertIn(gate.md5_file(self.mesh("run1")), md5sums)
        self.assertIn("# gate verdict: PASS", md5sums)
        info = gate.read_prereg_md5(prereg)
        self.assertEqual(info.declared, info.actual)
        self.assertIn(info.actual, md5sums)
        if sys.platform.startswith("linux"):
            peaks = [int(item) for item in re.findall(r"\((\d+) bytes", status)]
            self.assertGreaterEqual(len(peaks), 3)
            self.assertGreater(min(peaks), 2 * 1024 * 1024)

        again = self.run_gate(prereg)
        self.assertNotEqual(again, 0)
        self.assertTrue(self.gate_out.startswith("FAIL:"))
        self.assertIn("refusing to overwrite", self.gate_err)
        self.assertEqual(self.status_text(), status)
        self.assertEqual((self.root / "MD5SUMS").read_text(encoding="utf-8"), md5sums)
        self.assertEqual(log.read_text(encoding="utf-8"), "smoke out existed=0\nrun1 out existed=0\nrun2 out existed=0\n")
        self.assertEqual(self.mesh("run1").read_bytes(), run1_mesh)

    def test_output_dir_is_not_created_before_the_step(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(PASS_SCRIPT, encoding="utf-8")
        sample = self.root / "sample.txt"
        sample.write_text("sample\n", encoding="utf-8")
        log = self.root / "phases.log"
        cmd = self.command(script, ["{phase}", "{outdir}", str(sample), str(log)])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"input: sample.txt {gate.md5_file(sample)}",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 0)
        text = log.read_text(encoding="utf-8")
        self.assertEqual(text, "smoke out existed=0\nrun1 out existed=0\nrun2 out existed=0\n")
        for phase in ("smoke", "run1", "run2"):
            self.assertTrue(self.mesh(phase).is_file(), phase)
            self.assertTrue((self.root / "stage" / phase / "stdout.log").is_file(), phase)
            self.assertFalse((self.root / "stage" / phase / "out").is_file())

    def test_per_step_env_is_set_and_hashed(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(ENV_SCRIPT, encoding="utf-8")
        cmd = self.command(script, ["{phase}", "{outdir}"])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    "env: OMP_NUM_THREADS=1",
                    "env: MKL_NUM_THREADS=1",
                    "env: OPENBLAS_NUM_THREADS=1",
                    "smoke_env: LAYER_STEP=smoke",
                    "run_env: LAYER_STEP=run",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        parsed = gate.parse_prereg(prereg.read_text(encoding="utf-8"), prereg)
        smoke_env = gate.step_env(parsed, "smoke")
        run_env = gate.step_env(parsed, "run1")
        self.assertEqual(smoke_env[-1], ("LAYER_STEP", "smoke"))
        self.assertEqual(run_env[-1], ("LAYER_STEP", "run"))
        self.assertEqual(smoke_env[0], ("OMP_NUM_THREADS", "1"))
        smoke_digest = gate.env_md5(smoke_env)
        run_digest = gate.env_md5(run_env)
        self.assertNotEqual(smoke_digest, run_digest)
        old = os.environ.get("OMP_NUM_THREADS")
        os.environ["OMP_NUM_THREADS"] = "99"
        try:
            code = self.run_gate(prereg)
        finally:
            if old is None:
                os.environ.pop("OMP_NUM_THREADS", None)
            else:
                os.environ["OMP_NUM_THREADS"] = old
        self.assertEqual(code, 0)
        self.assertEqual(self.mesh("smoke").read_text(encoding="utf-8"), "1 1 1 smoke\n")
        self.assertEqual(self.mesh("run1").read_text(encoding="utf-8"), "1 1 1 run\n")
        self.assertEqual(self.mesh("run2").read_text(encoding="utf-8"), "1 1 1 run\n")
        status = self.status_text()
        md5sums = (self.root / "MD5SUMS").read_text(encoding="utf-8")
        self.assertIn(f"- smoke env_md5: {smoke_digest}", status)
        self.assertIn(f"- run env_md5: {run_digest}", status)
        self.assertIn(f"{smoke_digest}  env:smoke", md5sums)
        self.assertIn(f"{run_digest}  env:run", md5sums)
        self.assertNotIn("99", self.mesh("smoke").read_text(encoding="utf-8"))

    def test_prereg_md5_mismatch(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        marker = self.root / "RAN"
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"smoke: {self.command(script, ['{outdir}', str(marker)])}",
                    f"run: {self.command(script, ['{outdir}', str(marker)])}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        raw = prereg.read_bytes()
        bad = re.sub(br"prereg_md5: [0-9a-f]{32}", b"prereg_md5: " + b"0" * 32, raw, count=1)
        self.assertNotEqual(raw, bad)
        prereg.write_bytes(bad)
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "stage").exists())
        status = self.status_text()
        self.assertIn("prereg md5 mismatch", status)
        self.assertIn("MISMATCH", status)
        self.assertIn("state: not started", status)

    def test_prereg_md5_required(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        body = "\n".join(
            [
                f"script: pipeline.py {gate.md5_file(script)}",
                f"smoke: {self.command(script, ['{outdir}', str(self.root / 'RAN')])}",
                f"run: {self.command(script, ['{outdir}', str(self.root / 'RAN')])}",
                "output: mesh.obj",
                "staging: stage",
                "status: STATUS.md",
                "md5sums: MD5SUMS",
            ]
        )
        path = self.root / "PREREG.md"
        path.write_text("# test\n\n```prereg\n" + body + "\n```\n", encoding="utf-8")
        self.assertEqual(self.run_gate(path), 2)
        self.assertIn("prereg_md5", self.gate_err)
        self.assertFalse((self.root / "STATUS.md").exists())
        self.assertFalse((self.root / "stage").exists())

    def test_recheck_md5_before_each_step(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MUTATE_SCRIPT, encoding="utf-8")
        sample = self.root / "sample.txt"
        sample.write_text("sample\n", encoding="utf-8")
        cmd = self.command(script, ["{phase}", "{outdir}", str(sample)])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"input: sample.txt {gate.md5_file(sample)}",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertTrue(self.mesh("smoke").is_file())
        self.assertFalse((self.root / "stage" / "run1").exists())
        self.assertFalse((self.root / "stage" / "run2").exists())
        status = self.status_text()
        self.assertIn("- recheck before smoke: ok", status)
        self.assertIn("before run1:", status)
        self.assertIn("md5 mismatch", status)
        self.assertIn("state: not started", status)
        self.assertEqual(status.count("state: not started"), 2)

    def test_md5_mismatch(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        marker = self.root / "RAN"
        bad = "0" * 32
        self.assertNotEqual(gate.md5_file(script), bad)
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {bad}",
                    f"smoke: {self.command(script, ['{outdir}', str(marker)])}",
                    f"run: {self.command(script, ['{outdir}', str(marker)])}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "stage").exists())
        status = self.status_text()
        self.assertIn("- verdict: FAIL", status)
        self.assertIn("MISMATCH", status)
        self.assertIn("md5 mismatch", status)
        self.assertIn("state: not started", status)
        self.assertIn(bad, (self.root / "MD5SUMS").read_text(encoding="utf-8"))

    def test_run1_failure_does_not_start_run2(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(RUN1_FAIL_SCRIPT, encoding="utf-8")
        log = self.root / "phases.log"
        cmd = self.command(script, ["{phase}", "{outdir}", str(log)])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertEqual(log.read_text(encoding="utf-8"), "smoke\nrun1\n")
        self.assertTrue(self.mesh("smoke").is_file())
        self.assertTrue((self.root / "stage" / "run1").is_dir())
        self.assertFalse((self.root / "stage" / "run2").exists())
        status = self.status_text()
        self.assertIn("run1 exit code 1", status)
        self.assertIn("- verdict: FAIL", status)
        self.assertEqual(status.count("state: not started"), 1)
        self.assertIn("# run2: not started", (self.root / "MD5SUMS").read_text(encoding="utf-8"))

    def test_nondeterministic_outputs(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(NONDET_SCRIPT, encoding="utf-8")
        cmd = self.command(script, ["{outdir}"])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 1)
        run1 = self.mesh("run1")
        run2 = self.mesh("run2")
        self.assertTrue(run1.is_file())
        self.assertTrue(run2.is_file())
        self.assertNotEqual(run1.read_bytes(), run2.read_bytes())
        status = self.status_text()
        self.assertIn("output md5 mismatch for mesh.obj", status)
        self.assertIn("differ", status)
        self.assertIn("- verdict: FAIL", status)

    def test_refuse_to_overwrite_existing_output(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        marker = self.root / "RAN"
        target = self.root / "stage" / "run1" / "out" / "mesh.obj"
        target.parent.mkdir(parents=True)
        target.write_text("ORIGINAL\n", encoding="utf-8")
        prereg = self._runnable_prereg(script, marker)
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "stage" / "smoke").exists())
        self.assertFalse((self.root / "stage" / "run2").exists())
        self.assertIn("staging already exists", self.status_text())

    def test_refuse_to_overwrite_existing_status(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        marker = self.root / "RAN"
        status = self.root / "STATUS.md"
        status.write_text("ORIGINAL\n", encoding="utf-8")
        prereg = self._runnable_prereg(script, marker)
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertEqual(status.read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "stage").exists())

    def test_refuse_to_overwrite_existing_md5sums(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        marker = self.root / "RAN"
        md5sums = self.root / "MD5SUMS"
        md5sums.write_text("ORIGINAL\n", encoding="utf-8")
        prereg = self._runnable_prereg(script, marker)
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertEqual(md5sums.read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "stage").exists())
        status = self.status_text()
        self.assertIn("- verdict: FAIL", status)
        self.assertIn("refusing to overwrite", status)

    def test_stdio_logs_are_new_files(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(ENV_SCRIPT, encoding="utf-8")
        cmd = self.command(script, ["{phase}", "{outdir}"])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    "env: OMP_NUM_THREADS=1",
                    "env: MKL_NUM_THREADS=1",
                    "env: OPENBLAS_NUM_THREADS=1",
                    "smoke_env: LAYER_STEP=smoke",
                    "run_env: LAYER_STEP=run",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 0)
        for phase in ("smoke", "run1", "run2"):
            stdout = (self.root / "stage" / phase / "stdout.log").read_text(encoding="utf-8")
            stderr = (self.root / "stage" / phase / "stderr.log").read_text(encoding="utf-8")
            self.assertEqual(stdout, f"stdout {phase}\n")
            self.assertEqual(stderr, f"stderr {phase}\n")
            self.assertFalse((self.root / "stage" / phase / "out" / "stdout.log").exists())
        smoke_log = (self.root / "stage" / "smoke" / "stdout.log").read_bytes()
        self.assertNotEqual(self.run_gate(prereg), 0)
        self.assertEqual((self.root / "stage" / "smoke" / "stdout.log").read_bytes(), smoke_log)

    def test_memory_cap_kills_process_tree(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("process-tree RSS kill is verified on Linux")
        parent = self.root / "parent.py"
        child = self.root / "child.py"
        parent.write_text(TREE_PARENT, encoding="utf-8")
        child.write_text(TREE_CHILD, encoding="utf-8")
        pidfile = self.root / "child.pid"
        cmd = self.command(parent, ["{phase}", "{outdir}", str(child), str(pidfile)])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: parent.py {gate.md5_file(parent)}",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                    "memory_cap_mb: 64",
                ]
            )
        )
        started = time.monotonic()
        self.assertEqual(self.run_gate(prereg), 1)
        elapsed_wall = time.monotonic() - started
        status = self.status_text()
        self.assertIn("exceeds cap", status)
        self.assertLess(self.smoke_elapsed(status), 6)
        self.assertLess(elapsed_wall, 8)
        self.assertFalse((self.root / "stage" / "run1").exists())
        self.assertFalse((self.root / "stage" / "run2").exists())
        self.assertTrue(pidfile.is_file())
        pid = int(pidfile.read_text(encoding="utf-8"))
        time.sleep(0.2)
        state = gate._linux_state(pid)
        if state in ("R", "S", "D"):
            os.kill(pid, signal.SIGKILL)
            self.fail(f"child still running after the cap kill, state={state}")

    def test_free_ram_floor_blocks_start(self) -> None:
        free = gate.free_ram_bytes()
        if sys.platform.startswith("linux"):
            self.assertIsNotNone(free)
            self.assertGreater(free or 0, 1024 * 1024)
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        marker = self.root / "RAN"
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"smoke: {self.command(script, ['{outdir}', str(marker)])}",
                    f"run: {self.command(script, ['{outdir}', str(marker)])}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                    "free_ram_floor_mb: 99999999",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "stage").exists())
        self.assertIn("free RAM", self.status_text())

    def test_free_ram_floor_kills_running_step(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(SLEEP_SCRIPT, encoding="utf-8")
        flag = self.root / "flag.txt"
        cmd = self.command(script, ["{phase}", "{outdir}", str(flag)])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                    "free_ram_floor_mb: 1",
                ]
            )
        )
        real = gate.free_ram_bytes
        calls = {"n": 0}

        def fake() -> int:
            calls["n"] += 1
            if calls["n"] == 1:
                return 64 * 1024 * 1024 * 1024
            return 0

        gate.free_ram_bytes = fake
        try:
            code = self.run_gate(prereg)
        finally:
            gate.free_ram_bytes = real
        self.assertEqual(code, 1)
        self.assertGreaterEqual(calls["n"], 2)
        status = self.status_text()
        self.assertIn("below floor", status)
        self.assertFalse((self.root / "stage" / "run1").exists())
        text = flag.read_text(encoding="utf-8") if flag.exists() else ""
        self.assertNotIn("done", text)
        self.assertLess(self.smoke_elapsed(status), 6)

    def test_timeout_kills_and_skips_later_steps(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(SLEEP_SCRIPT, encoding="utf-8")
        flag = self.root / "flag.txt"
        cmd = self.command(script, ["{phase}", "{outdir}", str(flag)])
        prereg = self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"smoke: {cmd}",
                    f"run: {cmd}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                    "smoke_timeout_sec: 1",
                    "run_timeout_sec: 30",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 1)
        status = self.status_text()
        self.assertIn("timeout 1s", status)
        self.assertLess(self.smoke_elapsed(status), 6)
        self.assertFalse((self.root / "stage" / "run1").exists())
        self.assertFalse((self.root / "stage" / "run2").exists())
        self.assertEqual(status.count("state: not started"), 2)
        text = flag.read_text(encoding="utf-8") if flag.exists() else ""
        self.assertNotIn("done", text)
        self.assertIn("started", text)

    def test_memory_problem_rules(self) -> None:
        self.assertIsNone(gate.memory_problem("run1", 1024, None))
        self.assertIsNone(gate.memory_problem("run1", 1024 * 1024, 1))
        self.assertIsNotNone(gate.memory_problem("run1", 1024 * 1024 + 1, 1))
        self.assertIn("unavailable", gate.memory_problem("smoke", None, 32) or "")

    def test_example_prereg_matches_files(self) -> None:
        path = Path(__file__).resolve().parent / "examples" / "PREREG.example.md"
        prereg = gate.parse_prereg(path.read_text(encoding="utf-8"), path)
        info = gate.read_prereg_md5(path)
        self.assertEqual(info.declared, info.actual)
        self.assertEqual(prereg.declared_md5, info.declared)
        self.assertGreaterEqual(len(prereg.files), 1)
        for item in prereg.files:
            self.assertTrue(item.path.is_file(), item.path)
            self.assertEqual(gate.md5_file(item.path), item.md5)
        self.assertEqual(prereg.outputs, ["mesh.obj"])
        self.assertEqual(
            prereg.env,
            [
                ("OMP_NUM_THREADS", "1"),
                ("MKL_NUM_THREADS", "1"),
                ("OPENBLAS_NUM_THREADS", "1"),
            ],
        )
        self.assertIsNone(prereg.memory_cap_mb)
        self.assertIn("{outdir}", prereg.smoke)
        self.assertIn("{outdir}", prereg.run)
        out = gate.output_dir(prereg, "smoke")
        self.assertEqual(out.name, "out")
        self.assertTrue(str(out).endswith(f"{os.sep}smoke{os.sep}out"))

    def _runnable_prereg(self, script: Path, marker: Path) -> Path:
        return self.write_prereg(
            "\n".join(
                [
                    f"script: pipeline.py {gate.md5_file(script)}",
                    f"smoke: {self.command(script, ['{outdir}', str(marker)])}",
                    f"run: {self.command(script, ['{outdir}', str(marker)])}",
                    "output: mesh.obj",
                    "staging: stage",
                    "status: STATUS.md",
                    "md5sums: MD5SUMS",
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
