Stub. Last known: mailbox 192.168.0.228:8765, desk :8766, wired .113, dark after Tue 2026-08-25 2pm.

## Layer-improvement standard

Method changes on a layer follow section 4 of [Schedule and layer-improvement procedures (2026-10-31)](../procedures/PROCEDURES-SCHEDULE-AND-LAYER-OPS-20261031.md). The retired routines that text replaces are kept, unchanged, in [ROUTINE-ARCHIVE-PAUSED-20261031.md](../procedures/ROUTINE-ARCHIVE-PAUSED-20261031.md). Both files are append-only.

In short: write a PREREG with md5 sums of the scripts and inputs before any run, and do not tune after results. Smoke-test on synthetic input first. Then do a deterministic double run, strictly one after the other (run2 starts only after run1's exit code is read and is 0). Outputs of run1 and run2 must match by md5. Stop on the first FAIL and do not start the next revision automatically. Staging only, new files only, append-only history. Grades are evidence, not promotion. The rest of section 4 (what a desk may change, references, citations) stays in that file.

Pipeline machines can enforce the run sequence with the stdlib harness in [tools/gate](../../tools/gate/README.md).
