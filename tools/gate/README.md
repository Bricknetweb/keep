# Layer-improvement gate

A pipeline machine can copy this folder and run it with the system Python 3. It has no dependencies beyond the standard library (Python 3.9 or newer) and it behaves the same way on Windows and on macOS or Linux.

The gate enforces the layer-improvement run sequence from `docs/procedures/PROCEDURES-SCHEDULE-AND-LAYER-OPS-20261031.md` section 4. It does not decide the next revision. A FAIL stops in place. A PASS is a record that this PREREG's smoke test and double run agreed. Promotion stays with Jon.

```text
python3 tools/gate/gate.py path/to/PREREG.md
```

On Windows, `python` is the usual command name. Exit 0 means PASS. Exit 1 means FAIL. Exit 2 means the PREREG text or the command line is not usable, and in that case the gate writes nothing.

## What you write first

Write the PREREG before the run, with md5 sums of the scripts and of every input file the commands read. After you see results, leave that file alone. The next attempt gets a new PREREG and new output paths.

The gate reads one fenced block tagged `prereg`. The fence starts at the beginning of the line. Blank lines are ignored. A line whose first non-space character is `#` is a comment. Paths for `script`, `input`, `staging`, `status`, and `md5sums` are relative to the directory that contains the PREREG, unless they are absolute. Paths do not contain spaces.

```prereg
script: write_layer.py <md5>
input: synthetic.txt <md5>
input: sample.txt <md5>
smoke: python3 write_layer.py synthetic.txt {outdir}
run: python3 write_layer.py sample.txt {outdir}
output: mesh.obj
staging: staging/layer-r1
status: staging/layer-r1-STATUS.md
md5sums: staging/layer-r1-MD5SUMS
memory_cap_mb: 4096
```

| Key | Role |
| --- | --- |
| `script` | Repeat once per script file. Value is `path` then the md5. At least one. |
| `input` | Repeat once per input file, same shape as `script`. |
| `smoke` | Command for the synthetic-input smoke test. Required. |
| `run` | Command for both run1 and run2. Required. |
| `output` | Repeat once per file the run writes inside `{outdir}`. Relative name only (`mesh.obj` or `parts/mesh.obj`). At least one. |
| `staging` | A directory that is not already on disk. The gate creates it and puts `smoke`, `run1`, and `run2` underneath. |
| `status` | Path of a new STATUS markdown file. |
| `md5sums` | Path of a new MD5SUMS file. |
| `memory_cap_mb` | Optional. Peak resident-set cap for each command, in mebibytes (1024×1024). |

`staging`, `status`, and `md5sums` are three different paths. `status` and `md5sums` sit outside `staging/smoke`, `staging/run1`, and `staging/run2`. A worked file with real hashes is `examples/PREREG.example.md`. The stand-in script is `examples/write_layer.py`.

`{outdir}` and `{phase}` are replaced in each command argument. `{phase}` is `smoke`, `run1`, or `run2`. `{outdir}` is the absolute directory for that phase. Put the method in a script, hash that script, and point `smoke` and `run` at it. The gate splits the command with POSIX quoting on macOS and Linux, and with Windows quoting on Windows, then runs it with no shell. The working directory is the PREREG's directory. Stdin is closed. The environment also has `GATE_PHASE` and `GATE_OUTDIR`. Use forward slashes in paths inside the command.

`memory_cap_mb` is enforced when it is set. While the command runs, the gate samples its resident set (Linux `VmHWM` until the process exits, a macOS `ps` sample, or the Windows peak working set). On Linux and macOS it also keeps the kernel high-water mark from `getrusage` when this command raises it. The figure is for the command process itself, not every grandchild it might spawn. If a cap is set and no peak could be measured, the gate FAILs closed. Omit the key when you do not want a cap.

## What the gate does

It stops at the first FAIL. Later steps do not run.

1. Refuse when `staging`, the STATUS path, or the MD5SUMS path is already on disk. An existing staging directory also covers outputs left there by an earlier attempt.
2. Hash every listed script and input, in the order written. The first missing file or md5 mismatch is a FAIL. Nothing has been started.
3. Create `staging/smoke` and run the smoke command. Read its exit code.
4. On exit 0, and only if the memory cap holds, create `staging/run1` and run the run command. Read its exit code.
5. On exit 0, and only then, create `staging/run2` and run that same command again.
6. Hash each declared output from run1 and from run2. The first missing file or hash difference is a FAIL.
7. Write the STATUS markdown file and the MD5SUMS file. Both are created with an exclusive write, so an existing file is left unchanged.

Before each command it also refuses when that phase's output directory, or a declared output path inside it, is already present. It does not delete files, it does not overwrite files, and it does not open a follow-up revision.

STATUS and MD5SUMS record the verdict, the reason, each command that ran (and `not started` for a phase that did not), exit codes, start and finish times, elapsed seconds, and peak memory where the machine could measure it. MD5SUMS also lists the hex digests of the scripts, inputs, and outputs that were hashed. A PASS is exit 0 together with `verdict: PASS` in the new STATUS file.

Partial directories stay where they are after a FAIL. Point the next PREREG at new `staging`, `status`, and `md5sums` paths.

## Tests

```text
python3 tools/gate/test_gate.py
```

The tests cover a passing double run, an md5 mismatch, a run1 failure that must not start run2, outputs that differ between run1 and run2, and refusal to overwrite an existing output, STATUS file, or MD5SUMS file.
