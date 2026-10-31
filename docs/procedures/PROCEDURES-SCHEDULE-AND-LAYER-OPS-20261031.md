# Schedule and layer-improvement procedures (distilled 2026-10-31)
Source: the 16 retired Grok Bot routines (archive ROUTINE-ARCHIVE-PAUSED-20261031.md), reconciled with Jon's rulings through 2026-10-31. Where an old routine conflicts with a later ruling, the later ruling wins and is noted. New file; append-only.

## 1. Daily rhythm (current)
- Daytime (about 06:00–22:00 MT): Grok Bot check-ins every 2 hours when work is active (red/yellow/green per bot, usage forecast, standing-rule spot check). Morning and late-afternoon summaries come from those check-ins, not separate report routines.
- 22:00–06:00 MT: Cetus and the Sparks may run (only then, unless Jon OKs otherwise). Grok Bot goes quiet except for emergencies; machines continue on their own LaunchAgents, crons and task lists.
- First message after 06:00 carries the overnight summary.
- Emergencies that break quiet hours: dashboard down, runaway spawn, data loss, a mesh shrinking or failing QA, disk filling, both Sparks down, or a desk blocked with nothing next.
- One-off timed checks (holds, watchdog applies) are once-only routines with exact timing and are deleted after they fire.

## 2. Status reading order (each check)
1. STOP markers and STOP-STATE.json first (GROKBOT-OFF, AUTOMATION-HARD-STOP, STOP-AUTOMATED-WORKLOAD, per-desk STOP files). If set, report honestly and do not arm loops, bakes or model loads.
2. Keep's no-LLM audit: PIPELINE-AUDIT, LIVE-FACTS, PROGRESS-2-4-6H, MESH-QA-LATEST, /api/health.
3. Newest STATUS, PREREG and MD5SUMS in the dated exchange folders (ceo/exchange/ceogrok/out/<date>/, including sessions/mbp/claude/).
4. Ask an agent directly only if its files show no progress for over 2 hours (old routines used 20–45 min; relaxed to save usage).

## 3. Fixing things (from the hourly dashboard method)
- Act only on critical findings, or warnings that persist across two audits; confirm with raw evidence first.
- Smallest reversible fix: comment out a duplicate cron line rather than delete, stop one duplicate process, add a guard.
- Back up first (`cp -n`), md5 before and after, record the rollback command.
- At most one pipeline changed per hour unless an emergency; verify the previous change against the next audit and roll back if worse.
- Log every change in an append-only dated entry.

## 4. Layer-improvement procedure (current standard)
Old routines let agents "iterate shapes, no Jon wait" from a VL FAIL. That is superseded. The current rule:
1. PREREG with md5 before any method change; no tuning after results.
2. Smoke test on synthetic input first.
3. Deterministic double run, strictly one after the other (read run1's exit code before starting run2).
4. Stop on FAIL; the next revision needs Jon.
5. Staging only; m18 read-only; no scaling; 1 mm cap except where Jon ruled otherwise; no LLM-generated geometry.
6. One batch piece at a time per desk (from the Os bone-batch heal): no whole-skeleton thrash, no extra bones.
7. Model or VL grades (MedGemma, second-eye, 122B) are evidence, never promotion. A PASS never means promote; dual-model disagreement goes to review, not auto-iteration.
8. Reference plates for the layer under work should exist under ceo/reference/anatomy/ before grading; if the references are thin, say so rather than trusting weak reviews.
9. Every citation archived for the pre-release accuracy check; no NC, SA or ND sources.

## 5. Model routing (Sept 2026 lessons, check before reuse)
- Spark-A 122B: analysis, steering and MOE review (short first, then expand; no hard token caps).
- Spark-B: MedGemma medical grades through the gate only when needed; Cyber-Tiel for chat. Never use the grade alias for chat.
- Forge 3090: ComfyUI only when cleared; don't take its jobs.
- Usage as of 2026-10-31: heavy drafting (PREREGs, scripts, reviews) goes to Claude Code on the MacBook Pro; Gemini (agy) for literature and second reviews within its quota; Grok agents check, run and relay with short reports.

## 6. Hard lines carried forward
- Never flash the visor unless Jon types "flash it". Nothing is promoted without Jon.
- Never delete data. New files only.
- No messages to Slack, email or outside chats without Jon's go-ahead; anatomy images stay out of Slack.
- An agent's word is never Jon's approval.

## 7. Open items surfaced by the archive
- Factry NPU Gemma token metering (usage log after generate() in npu_gemma_server.py, then factry_ctl restart-npu; context in ceo/TOKEN-USAGE-AUDIT-20261005.md). The reminder never fired; status unknown.
- Sept routines name the live Os as 562b91c2. The skeleton master is now m18 (lineage 9c3ba14d), so treat 562b91c2 references as historical.
