"""Unit tests for the layer-improvement gate.

Run from the repo root:

    python3 tools/gate/test_gate.py
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate


PASS_SCRIPT = """\
import sys
from pathlib import Path

phase, outdir, infile, log = sys.argv[1:5]
with Path(log).open("a", encoding="utf-8") as handle:
    handle.write(phase + "\\n")
data = Path(infile).read_bytes()
(Path(outdir) / "mesh.obj").write_bytes(b"solid\\n" + data)
"""

RUN1_FAIL_SCRIPT = """\
import sys
from pathlib import Path

phase, outdir, log = sys.argv[1:4]
with Path(log).open("a", encoding="utf-8") as handle:
    handle.write(phase + "\\n")
if phase == "run1":
    raise SystemExit(1)
(Path(outdir) / "mesh.obj").write_bytes(b"solid\\n")
"""

NONDET_SCRIPT = """\
import sys
from pathlib import Path

outdir = Path(sys.argv[1])
(outdir / "mesh.obj").write_text(str(outdir.resolve()) + "\\n", encoding="utf-8")
"""

MARKER_SCRIPT = """\
import sys
from pathlib import Path

Path(sys.argv[2]).write_text("ran\\n", encoding="utf-8")
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
        path.write_text("# test prereg\n\n```prereg\n" + body.strip() + "\n```\n", encoding="utf-8")
        return path

    def command(self, script: Path, args: list[str]) -> str:
        parts = [sys.executable, str(script), *args]
        for part in parts:
            if any(ch.isspace() for ch in part):
                self.fail(f"test path has whitespace and would split: {part}")
        return " ".join(parts)

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
        self.assertEqual(log.read_text(encoding="utf-8"), "smoke\nrun1\nrun2\n")
        smoke_mesh = (self.root / "stage" / "smoke" / "mesh.obj").read_bytes()
        run1_mesh = (self.root / "stage" / "run1" / "mesh.obj").read_bytes()
        run2_mesh = (self.root / "stage" / "run2" / "mesh.obj").read_bytes()
        self.assertEqual(smoke_mesh, b"solid\n" + synthetic.read_bytes())
        self.assertEqual(run1_mesh, b"solid\n" + sample.read_bytes())
        self.assertEqual(run2_mesh, run1_mesh)
        status = (self.root / "STATUS.md").read_text(encoding="utf-8")
        md5sums = (self.root / "MD5SUMS").read_text(encoding="utf-8")
        self.assertIn("- verdict: PASS", status)
        self.assertEqual(status.count("elapsed_sec:"), 3)
        self.assertEqual(status.count("exit_code:"), 3)
        self.assertEqual(status.count("peak_rss:"), 3)
        self.assertIn("match", status)
        self.assertIn(gate.md5_file(self.root / "stage" / "run1" / "mesh.obj"), md5sums)
        self.assertIn("# gate verdict: PASS", md5sums)
        if sys.platform.startswith("linux"):
            peaks = [int(item) for item in re.findall(r"\((\d+) bytes", status)]
            self.assertGreaterEqual(len(peaks), 3)
            self.assertGreater(min(peaks), 2 * 1024 * 1024)

        again = self.run_gate(prereg)
        self.assertNotEqual(again, 0)
        self.assertTrue(self.gate_out.startswith("FAIL:"))
        self.assertIn("refusing to overwrite", self.gate_err)
        self.assertEqual((self.root / "STATUS.md").read_text(encoding="utf-8"), status)
        self.assertEqual((self.root / "MD5SUMS").read_text(encoding="utf-8"), md5sums)
        self.assertEqual(log.read_text(encoding="utf-8"), "smoke\nrun1\nrun2\n")
        self.assertEqual((self.root / "stage" / "run1" / "mesh.obj").read_bytes(), run1_mesh)

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
        status = (self.root / "STATUS.md").read_text(encoding="utf-8")
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
        self.assertTrue((self.root / "stage" / "smoke" / "mesh.obj").is_file())
        self.assertTrue((self.root / "stage" / "run1").is_dir())
        self.assertFalse((self.root / "stage" / "run2").exists())
        status = (self.root / "STATUS.md").read_text(encoding="utf-8")
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
        run1 = self.root / "stage" / "run1" / "mesh.obj"
        run2 = self.root / "stage" / "run2" / "mesh.obj"
        self.assertTrue(run1.is_file())
        self.assertTrue(run2.is_file())
        self.assertNotEqual(run1.read_bytes(), run2.read_bytes())
        status = (self.root / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("output md5 mismatch for mesh.obj", status)
        self.assertIn("differ", status)
        self.assertIn("- verdict: FAIL", status)

    def test_refuse_to_overwrite_existing_output(self) -> None:
        script = self.root / "pipeline.py"
        script.write_text(MARKER_SCRIPT, encoding="utf-8")
        marker = self.root / "RAN"
        target = self.root / "stage" / "run1" / "mesh.obj"
        target.parent.mkdir(parents=True)
        target.write_text("ORIGINAL\n", encoding="utf-8")
        prereg = self._runnable_prereg(script, marker)
        self.assertEqual(self.run_gate(prereg), 1)
        self.assertEqual(target.read_text(encoding="utf-8"), "ORIGINAL\n")
        self.assertFalse(marker.exists())
        self.assertFalse((self.root / "stage" / "smoke").exists())
        self.assertFalse((self.root / "stage" / "run2").exists())
        status = self.root / "STATUS.md"
        self.assertTrue(status.is_file())
        self.assertIn("staging already exists", status.read_text(encoding="utf-8"))

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
        status = (self.root / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("- verdict: FAIL", status)
        self.assertIn("refusing to overwrite", status)

    def test_memory_cap_stops_later_phases(self) -> None:
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
                    "memory_cap_mb: 1",
                ]
            )
        )
        self.assertEqual(self.run_gate(prereg), 1)
        text = log.read_text(encoding="utf-8")
        self.assertIn("smoke", text)
        self.assertNotIn("run1", text)
        self.assertNotIn("run2", text)
        self.assertFalse((self.root / "stage" / "run1").exists())
        self.assertFalse((self.root / "stage" / "run2").exists())
        status = (self.root / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("exceeds cap", status)
        self.assertEqual(status.count("state: not started"), 2)

    def test_memory_problem_rules(self) -> None:
        self.assertIsNone(gate.memory_problem("run1", 1024, None))
        self.assertIsNone(gate.memory_problem("run1", 1024 * 1024, 1))
        self.assertIsNotNone(gate.memory_problem("run1", 1024 * 1024 + 1, 1))
        self.assertIn("unavailable", gate.memory_problem("smoke", None, 32) or "")

    def test_example_prereg_matches_files(self) -> None:
        path = Path(__file__).resolve().parent / "examples" / "PREREG.example.md"
        prereg = gate.parse_prereg(path.read_text(encoding="utf-8"), path)
        self.assertGreaterEqual(len(prereg.files), 1)
        for item in prereg.files:
            self.assertTrue(item.path.is_file(), item.path)
            self.assertEqual(gate.md5_file(item.path), item.md5)
        self.assertEqual(prereg.outputs, ["mesh.obj"])
        self.assertIsNone(prereg.memory_cap_mb)
        self.assertIn("{outdir}", prereg.smoke)
        self.assertIn("{outdir}", prereg.run)

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
