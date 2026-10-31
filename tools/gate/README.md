# Layer-improvement gate

A pipeline machine can copy this folder and run it with the system Python 3. It has no dependencies beyond the standard library (Python 3.9 or newer) and it behaves the same way on Windows and on macOS or Linux.

The gate enforces the layer-improvement run sequence from `docs/procedures/PROCEDURES-SCHEDULE-AND-LAYER-OPS-20261031.md` section 4. It does not decide the next revision. A FAIL stops in place. A PASS is a record that this PREREG's smoke test and double run agreed. Promotion stays with Jon.

```text
python3 tools/gate/gate.py path/to/PREREG.md
```

On Windows, `python` is the usual command name. Exit 0 means PASS. Exit 1 means FAIL. Exit 2 means the PREREG text or the command line is not usable, and in that case the gate writes nothing.

## What you write first

Write the PREREG before the run, with md5 sums of the scripts, of every input file the commands read, and of the PREREG file itself. After you see results, leave that file alone. The next attempt gets a new PREREG and new output paths.

The gate reads one fenced block tagged `prereg`. The fence starts at the beginning of the line. Blank lines are ignored. A line whose first non-space character is `#` is a comment. Paths for `script`, `input`, `staging`, `status`, and `md5sums` are relative to the directory that contains the PREREG, unless they are absolute. Paths do not contain spaces.

```prereg
prereg_md5: <md5 of this file with this line removed>
script: write_layer.py <md5>
input: synthetic.txt <md5>
input: sample.txt <md5>
env: OMP_NUM_THREADS=1
env: MKL_NUM_THREADS=1
env: OPENBLAS_NUM_THREADS=1
smoke_env: LAYER_STEP=smoke
run_env: LAYER_STEP=run
smoke: python3 write_layer.py synthetic.txt {outdir}
run: python3 write_layer.py sample.txt {outdir}
output: mesh.obj
staging: staging/layer-r1
status: staging/layer-r1-STATUS.md
md5sums: staging/layer-r1-MD5SUMS
memory_cap_mb: 4096
free_ram_floor_mb: 512
timeout_sec: 3600
smoke_timeout_sec: 120
run_timeout_sec: 3600
```

| Key | Role |
| --- | --- |
| `prereg_md5` | Required. Column 0. md5 of the file with this one line removed. |
| `script` | Repeat once per script file. Value is `path` then the md5. At least one. |
| `input` | Repeat once per input file, same shape as `script`. |
| `env` | Repeat for `NAME=VALUE` applied to every step. Later `smoke_env` or `run_env` for the same name wins. |
| `smoke_env` | Same shape as `env`, added for the smoke step only. |
| `run_env` | Same shape as `env`, added for run1 and run2. |
| `smoke` | Command for the synthetic-input smoke test. Required. |
| `run` | Command for both run1 and run2. Required. |
| `output` | Repeat once per file the run writes inside `{outdir}`. Relative name only (`mesh.obj` or `parts/mesh.obj`). At least one. |
| `staging` | A directory that is not already on disk. The gate creates `staging/<phase>/` for logs. |
| `status` | Path of a new STATUS markdown file. |
| `md5sums` | Path of a new MD5SUMS file. |
| `memory_cap_mb` | Optional. While a step runs, kill it when the process tree's RSS goes over this many mebibytes (1024×1024). |
| `free_ram_floor_mb` | Optional. Do not start a step, and kill a running step, when available RAM is below this many mebibytes. |
| `timeout_sec` | Optional. Kill a step that is still running after this many seconds. |
| `smoke_timeout_sec` | Optional. Timeout for smoke. Overrides `timeout_sec` for that step. |
| `run_timeout_sec` | Optional. Timeout for run1 and run2. Overrides `timeout_sec` for those steps. |

`staging`, `status`, and `md5sums` are three different paths. `status` and `md5sums` sit outside `staging/smoke`, `staging/run1`, and `staging/run2`. A worked file with real hashes is `examples/PREREG.example.md`. The stand-in script is `examples/write_layer.py`.

To fill in `prereg_md5`, write the file without that line, hash those exact bytes, then insert a column-0 line `prereg_md5: <hash>` inside the fence. The gate deletes that one line and hashes what remains. Do not edit the hash to force a pass; write a new PREREG.

`{outdir}` and `{phase}` are replaced in each command argument. `{phase}` is `smoke`, `run1`, or `run2`. `{outdir}` is the absolute path `staging/<phase>/out`. The gate does not create that directory. The step creates it, so a script can assert that it is absent at start. The gate does create `staging/<phase>/` and, inside it, new `stdout.log` and `stderr.log` files for the step's stdout and stderr.

Put the method in a script, hash that script, and point `smoke` and `run` at it. The gate splits the command with POSIX quoting on macOS and Linux, and with Windows quoting on Windows, then runs it with no shell. The working directory is the PREREG's directory. Stdin is closed. On macOS and Linux the step is its own process group so a kill reaches the whole tree. The environment also has `GATE_PHASE`, `GATE_OUTDIR`, and `PYTHONUNBUFFERED=1`. Those three are injected by the gate and are not part of the env hash. Use forward slashes in paths inside the command.

The env hash is the md5 of the `NAME=VALUE` lines for that step, in declaration order, one per line, including the trailing newline. `smoke_env` overrides `env` for smoke. `run_env` overrides `env` for run1 and run2. The digest is written into STATUS and MD5SUMS.

`memory_cap_mb`, when set, is enforced while the step runs. About every 10ms the gate sums the current RSS of the step and its descendants (Linux `VmRSS` via `/proc`, macOS `ps`, Windows working sets). Over the cap, it kills the tree and does not start the next step. If the cap is set and no sample was possible, the step FAILs closed. `free_ram_floor_mb` uses Linux `MemAvailable`, a macOS `vm_stat` free+inactive+speculative estimate, or Windows available physical memory. A floor that cannot be measured FAILs closed before the step starts. `timeout_sec` and the per-step overrides kill the tree when the time is up.

## What the gate does

It stops at the first FAIL. Later steps do not run.

1. Refuse when `staging`, the STATUS path, or the MD5SUMS path is already on disk.
2. Check `prereg_md5`, then every listed script and input, in the order written. The first miss is a FAIL. Nothing has been started.
3. Immediately before smoke, hash the PREREG, scripts, and inputs again. On a miss, do not start smoke.
4. Create `staging/smoke/` and the new log files only. `{outdir}` (`staging/smoke/out`) is still absent. Run smoke. While it runs, kill the process tree if RSS, free RAM, or the timeout says so. Read the exit code.
5. On exit 0, recheck the hashes, then do the same for run1. run2 is not started unless that exit code is 0.
6. On exit 0, recheck the hashes again, then run run2 the same way.
7. Hash each declared output from `staging/run1/out` and `staging/run2/out`. The first missing file or hash difference is a FAIL.
8. Write the STATUS markdown file and the MD5SUMS file. Both are created with an exclusive write, so an existing file is left unchanged.

It does not delete files, it does not overwrite files, and it does not open a follow-up revision.

STATUS and MD5SUMS record the verdict, the reason, the PREREG md5, the env md5, each command that ran (and `not started` for a phase that did not), exit codes, start and finish times, elapsed seconds, peak process-tree RSS where it could be sampled, log paths, and any kill reason. A PASS is exit 0 together with `verdict: PASS` in the new STATUS file.

Partial directories stay where they are after a FAIL. Point the next PREREG at new `staging`, `status`, and `md5sums` paths.

## Tests

```text
python3 tools/gate/test_gate.py
```

The tests cover a passing double run, an output directory the step creates itself, per-step environment variables and their md5, the PREREG file's own md5, a recheck of script and input md5s before each step, an md5 mismatch, a run1 failure that must not start run2, outputs that differ between run1 and run2, refusal to overwrite, stdout and stderr logs, a memory-cap kill of the process tree, a free-RAM floor, and a per-step timeout.
