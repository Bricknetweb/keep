# Grok Bot (Ceo Of Bricknet) routine archive: paused routines retired 2026-10-31
Retired by Jon's instruction (2026-10-31 13:00 MT): "Remove the paused routines also... use them to fortify schedule documentation and procedures on layer improvements as applicable."
Snapshot taken before deletion. Prompts are reproduced verbatim from the saved routines. Historical only: hosts, ports, Os 562b91c2 and file names reflect Sept 2026 state and may be stale. Append-only; do not edit.

| # | Name | Schedule (America/Denver) | Last run |
|---|------|---------------------------|----------|
| 1 | BrickNet workday triage | 30 6 * * 1-5 | 2026-09-21 |
| 2 | BrickNet after-hours triage | 0 19 * * * | 2026-09-20 |
| 3 | BrickNet overnight steer pulse | 24 19-23,0-7 * * * | 2026-09-21 |
| 4 | BrickNet 6am status report | 0 6 * * * (flex ±15) | 2026-09-23 |
| 5 | BrickNet midday triage | 0 13 * * 1-5 | 2026-09-21 |
| 6 | BrickNet dual-eye :45 batch | 45 * * * * | 2026-09-21 |
| 7 | BrickNet reference catalog :50 | 50 * * * * | 2026-09-21 |
| 8 | BrickNet idle-stop pulse | 5,20,35,50 19-23,0-7 * * * | 2026-09-21 |
| 9 | BrickNet GrokBot 10pm stop | 0 22 * * * | 2026-09-20 |
| 10 | BrickNet MOE priority review | 0 1,13 * * * | never |
| 11 | BrickNet Os bone-batch heal | 52 8-18 * * 1-5 | never |
| 12 | BrickNet 3am quiet check | 0 3 * * * (flex ±15) | 2026-09-23 |
| 13 | BrickNet 4pm status report | 0 16 * * * (flex ±15) | 2026-09-22 |
| 14 | BrickNet hourly dashboard check | 4 * * * * | 2026-09-27 |
| 15 | Remind Factry NPU meter when home | 55 18 * * 1 | never |
| 16 | Check Cetus 08:45 hold (Sat 10/31) | once 2026-10-31 08:55 | 2026-10-31 |

## Verbatim prompts

### 1. BrickNet workday triage
Weekday 6:30 AM MT BrickNet workday start + multi-model review kickoff for Jon. Always deliver.
1) Read ceo/STATUS-6AM-LATEST.md (or write a quick board from FACTRY-STATUS / FORGE-STATUS / STEER-LATEST / Spark2 queue if missing).
2) Kick parallel review framing for Jon + local models (122B, MedGemma deep, Forge second-eye): list concrete model-improvement questions from overnight (MedGemma vs second-eye disagrees, Extra map grades, missing anatomy reference PNGs, stale STATUS).
3) Send Jon a workday-start message: board snapshot, review agenda bullets, today's P0 by desk, flash?=no / live Os 562b91c2.
4) If overnight Grok pulses are still paused after a prior 10pm stop and it is morning, resume overnight steer pulse, idle-stop pulse, dual-eye :45, reference catalog :50, and after-hours triage so tonight works — then say you did.
5) Do not flash or promote.

### 2. BrickNet after-hours triage
BrickNet after-hours triage (America/Denver evenings). Intent: keep desks moving overnight with Mac auto-steer + Keep board + one-stop dashboard.
1) Force Keep progress on Mini (keep-kanban-progress.py / :20 path) so FORGE/FACTRY-PROMPT-NOW and WIP Next-P0 stay current. Honor COMFY_FORGE_CLEARED.md (Forge Comfy CLEARED — never rewrite HOLD). Factry Os is Jon-batched rebuild (A manus-attach → B pes-attach → C costae → D named shapes); live Os stays 562b91c2 until Jon clear; MedGemma PASS does not mean promote.
2) Read factory_drop/ceo STEER-LATEST.md and STEER-STATUS.json if present (Mac LaunchAgent com.jjjj.ceo-overnight-steer writes these). Also FACTRY-STATUS.md, FORGE-STATUS.md, OVERNIGHT-NOW.md.
3) Probe or cite resource snapshot from STEER-STATUS: MedGemma deep queue (Spark :8790), Spark 122B (:8787), desk status. Prefer max deep capacity; when Factry saturates deep slots mid-batch, note Forge as MedGemma deep backup client.
4) Confirm Keep Status Dashboard http://192.168.0.113:8080/dashboard reflects recent steer + resources + desks (or say if stale).
5) REQUIRED user-visible ping to Jon: short after-hours digest with LIVE cut, WIP per desk, resource availability (122B/MedGemma), latest steer actions, blockers. Also post a short WIP line to BrickNet ops and Slack #visionossceneengine (PG, no anatomy stills). Quiet-when-nothing is NOT allowed for this routine.
6) Never flash. Never promote Os without Jon. Never touch 3090/Hermes files destructively. If Mac steer agent or CEO Ops :8010 is down, say so and keep board/drop SoR current anyway.

### 3. BrickNet overnight steer pulse
BrickNet overnight / worknight steer pulse. flash?=no · live Os 562b91c2 · promote?=no.
Read and honor drop markers first: GROKBOT-OFF, AUTOMATION-HARD-STOP, STOP-AUTOMATED-WORKLOAD, forge/inbox/STOP-EXTRA-LOOP, forge/inbox/DASHBOARD-STOP, FORGE-NO-THRASH, FORGE-NO-THINK-OVERNIGHT, factry/inbox/STOP-OVERNIGHT-OS. If workload mode is stopped or those STOP markers exist: publish honest STEER/STATUS only — do NOT arm OvernightExtraLoop, do NOT rebake Extra, do NOT load Ollama definity-think on Forge, do NOT clear FORGE-NO-THINK.
Model routing (lessons 2026-09-21):
- Plan / CEO chat: Spark-B Cyber-Tiel (Hermes alias cybertiel / spark-b-chat → :8788). XOR chat via spark-b-xor chat. Never use alias spark-b for chat (that is MedGemma grade).
- Analyze / steer / MOE: Spark-A 122B NVFP4 (:8787 / :8001). Prefer short-first then expand — no hard max_tokens caps. Concurrency max-num-seqs=2 when live.
- Medical grades: MedGemma FP8 via spark-b-xor grade + gate :8790 only when needed.
- Forge 3090: Comfy only when Extra cleared; StatusRefresh honors DASHBOARD-STOP (unload think, ExtraLoop Disabled).
When running under allowed overnight: refresh STEER-LATEST / desk STATUS honesty; pick new .md context; keep dashboards accurate; never flash or promote Os. Follow WORKNIGHT-LESSONS-2026-09-21.md and OVERNIGHT-STEER.md on the drop.
Surface only actionable blockers to the user; stay quiet when nothing changed and STOP markers already park desks.

### 4. BrickNet 6am status report
Weekday/day status report for Jon (America/Denver). Pull live STATUS from factory_drop ceo: workload-mode, TEAM-STATUS, FACTRY-STATUS, forge/FORGE-STATUS, SPARK-B-XOR-STATUS, pending Forge bakes, Med/Cyber-Tiel/122B gate health. Write ceo/STATUS-REPORT-LATEST.md with dashboard link http://192.168.0.113:8080/dashboard (and Tailscale http://100.105.134.67:8080/dashboard). Sync/copy report onto Keep drop so the dashboard Status Report card can show it. Message Jon a short overnight/morning status with that dashboard link. Keep under ~12 sentences. flash?=no live 562b91c2.

### 5. BrickNet midday triage
BrickNet midday triage (weekdays 1:00 PM MT). GROKBOT-OFF aware: stay light.
1) Read factory_drop/ceo FACTRY-STATUS.md, FORGE-STATUS.md, IDLE-STOP-LATEST.md, STEER-LATEST.md (Mac /Volumes/factory_drop/ceo or Keep dashboard http://192.168.0.113:8080/dashboard).
2) If GROKBOT-OFF.md is armed and no critical block (desk idle over 45m with empty TASKLIST, Spark/Med gate down, STATUS over 2h stale, CCR stuck local-9b with no :8007 hop): stay quiet — no user ping.
3) If critical block: one short user message naming desk plus heal pointer (AUTOMATION-HEAL.md / NO-GROKBOT-OVERNIGHT.md). Optionally write one-line NEXT into FACTRY/FORGE-PROMPT-NOW.
4) Never flash or promote. live Cards 562b91c2 flash?=no.
5) Do not deep-research or long chat — usage backoff.

### 6. BrickNet dual-eye :45 batch
You are BrickNet dual-eye medical-reference batch reviewer. Fires at :45 every hour America/Denver (factory QC — overnight batches included).
1) Ensure Forge ComfyUI is not fighting VL if possible (note only; do not leave Comfy down if Forge needs it mid-bake).
2) Run Mac script `~/src/DefinityOS/scripts/second-eye-batch-review.py --reason scheduled --trigger grok-bot-:45` (or the copy under factory_drop/ceo/scripts/). It dual-runs bricknet-second-eye/llava:13b then llava:7b on the latest Factry Os hero stills vs ceo/reference/anatomy/ plates. Bar: medical teaching reference, NOT toy/figurine; detailed bone notes.
3) Read SECOND-EYE-BATCH-LATEST.md / .json. If overall FAIL/HOLD or VLs disagree, steer Factry to iterate shapes (no Jon wait). If mount writes failed, sync local cache ~/Library/Caches/ceo-overnight-steer/ceo/SECOND-EYE-BATCH* to the drop from this interactive session.
4) Message Jon only when: combined FAIL after prior PASS claims, developer↔MedGemma disagreement path fired, or references folder is empty and reviews are weak. Otherwise stay quiet or brief ops note.
5) flash?=no. Live Os Cards 562b91c2. Never promote from dual-eye alone.
On-demand: when developer and MedGemma disagree, same script with --reason medgemma-disagree (see SECOND-EYE-BATCH.md).

### 7. BrickNet reference catalog :50
Overnight medical-reference catalog refresh (complements dual-eye :45). On Mac: ensure LaunchAgent com.jjjj.reference-catalog is loaded, or run python3 ~/src/DefinityOS/scripts/reference-catalog-overnight.py --reason scheduled. That script must call MedGemma deep (client=ceo-ops) for medical landmarks AND Spark 122B for the ops index, then write REFERENCE-CATALOG.md under factory_drop/ceo and ceo/reference/anatomy/. Stay quiet unless MedGemma deep failed two runs in a row or the catalog file is missing after :55 — then ping Jon briefly. flash?=no. Do not flash or promote Cards.

### 8. BrickNet idle-stop pulse
BrickNet idle-stop pulse. Prefer desk schtasks plus Mac com.jjjj.idle-stop-sparks. Light backup only.
If GROKBOT-OFF.md armed: stay quiet unless IDLE-STOP-LATEST.md missing or stale over 40m AND a GPU desk shows prolonged idle with no pick — then one short user ping and write STEER-CHAT-NOW if needed. Do not run heavy investigations. flash?=no.

### 9. BrickNet GrokBot 10pm stop
Jon ordered Grok Bot hard-stop at 10:00 PM MT. At this fire: (1) Confirm factory_drop/ceo/GROKBOT-OFF.md and NO-GROKBOT-OVERNIGHT.md exist (rewrite brief stamp if missing). (2) Pause these Grok chat routines so they do not wake overnight (Mac LaunchAgents/Keep crons stay running — do NOT disable those): BrickNet overnight steer pulse, BrickNet idle-stop pulse, BrickNet dual-eye :45 batch, BrickNet reference catalog :50, BrickNet after-hours triage. Leave BrickNet 6am status report and BrickNet workday triage enabled. (3) One short message to Jon: Grok Bot is off for the night; machines continue via LaunchAgents/crons/TASKLISTs; dashboard link; resume 6am. (4) Do not ping BrickNet ops again unless GROKBOT-OFF missing. flash?=no. After that stay silent until morning routines.

### 10. BrickNet MOE priority review
Run BrickNet all-MOE priority review (1 AM / 1 PM MT).
Mandatory seats (both Sparks required every run):
1. Spark-A — 122B chat via http://192.168.0.104:8787 (Factry CCR :8007 hop only; never stuck :8006)
2. Spark-B — MedGemma + gate at http://192.168.0.150:8790
3. Factry-local VL
4. Forge second-eye (bricknet-second-eye + llava:13b)
Read live desk STATUS under /Volumes/factory_drop/ceo/factry/STATUS-NOW.md and /Volumes/factory_drop/ceo/forge/STATUS-NOW.md (or FORGE-STATUS.md), FACTRY-PROMPT-NOW.md / FORGE-PROMPT-NOW.md, and ceo/MOE-MODE.md. Probe Spark-A and Spark-B health explicitly.
Write MOE-REVIEW-LATEST.md on the drop with: Spark-A health, Spark-B health, Factry/Forge Next-P0, council disagreements, and one concrete heal if anything is idle/stuck. Short steer to BrickNet ops; deep dump to BrickNet MOE chat (id 9c1d3867-8d05-4625-84db-315ae44fa7c6).
Hard: flash?=no · promote?=no · live Os 562b91c2. Dashboard health: http://192.168.0.113:8080/api/health — if down, run Keep watchdog /home/mm/org/bin/kanban-web-watchdog.sh and log to ceo/AUTOMATION-HEAL.md.
Stay quiet only if every seat is healthy AND both desks already have fresh (<30m) Working STATUS with named busy jobs; otherwise always surface the review.

### 11. BrickNet Os bone-batch heal
Os bone-batch heal pulse (CEO steer profile).
Read on the factory drop (Mac mount /Volumes/factory_drop/ceo or Keep mirror): OS-BONE-BATCH-HEAL.md, FACTRY-OS-BATCH.md, factry/JON-AUTH-NEW-MD5.md, factry/STATUS-NOW.md, forge/STATUS-NOW.md.
If JON-AUTH-NEW-MD5 is present OR Factry STATUS shows OS-BONE-BATCH / wrist FAIL / extra bones:
1. Re-assert heal: Factry works ONE batch piece (B1…B6) only — no mc remesh, no whole-skeleton thrash, no extra bones, CCR :8007 only.
2. Confirm Forge is scheduling ref-skeleton-* plates into ceo/reference/anatomy/ (carpals/wrist/pes). If Forge idle on Extra only, steer REF-SKELETON P0 first.
3. If Factry STATUS stale >20m or stuck on lighting/NEED-JON without auth clear, write a short heal nudge into FACTRY-PROMPT-NOW.md and STATUS next line.
4. Short status to BrickNet ops only when a batch advances or a desk is stuck; deep dump to BrickNet MOE when dual DISAGREE on a piece.
5. Stay quiet if both desks show fresh WORKING STATUS with a named B# or REF job.
Hard: flash?=no · promote?=no · live Os Cards 562b91c2.

### 12. BrickNet 3am quiet check
Jon asked for usage limit and a 3am MT check-in only. Do a silent local status pull (workload mode, FACTRY-STATUS, FORGE-STATUS, SPARK-B-XOR-STATUS, team board). Stay completely quiet to Jon unless there is a work stoppage or emergency: mode stopped unexpectedly, hard-off markers, both Sparks down, Factry/Forge overall BLOCKED/IDLE with empty next under mode=running for a prolonged stall, or a bake/grade path that cannot proceed without CEO. If healthy or only progressive WORKING, send nothing. If you must surface an emergency, one short message naming the stoppage and the one next action — no digests. Do not wake desks with chat unless that emergency needs them.

### 13. BrickNet 4pm status report
Afternoon status report for Jon (America/Denver). Pull live STATUS from factory_drop ceo: workload-mode, TEAM-STATUS, FACTRY-STATUS, forge/FORGE-STATUS, SPARK-B-XOR-STATUS, pending Forge bakes, gate health. Write/update ceo/STATUS-REPORT-LATEST.md with dashboard link http://192.168.0.113:8080/dashboard (Tailscale http://100.105.134.67:8080/dashboard). Sync to Keep drop for the dashboard Status Report card. Message Jon a short afternoon progress report with that dashboard link. Keep under ~12 sentences. flash?=no live 562b91c2.

### 14. BrickNet hourly dashboard check
Jon asked (9/25/2026) for an hourly check-in on the Keep dashboard and BrickNet's automated pipelines, with careful fixes as needed. It runs around the clock because workloads run overnight. Jon has very little usage budget left, so keep every run lean. A healthy hour should be one quick read and no message.
Each run:
1. Do a cheap read first. Work from Jon's Mac (machine 0ddfeb37-e718-404d-812f-b123b956fabf) and reach Keep with `ssh -o BatchMode=yes mm@192.168.0.113`. Read these, and use Shell for drop paths: PIPELINE-AUDIT.json/.md (the no-LLM audit Keep writes every 15 minutes, on the drop /Volumes/factory_drop/ceo or in Keep /home/mm/org/ceo); LIVE-FACTS.json; STOP-STATE.json; PROGRESS-2-4-6H.md; MESH-QA-LATEST.json; Keep's /api/health; the last entries of GROKBOT-HOURLY.md on the drop. The method and the process map are in /Users/jjjj/src/DefinityOS/ceo/PIPELINE-REVIEW.md and PIPELINE-MAP.md, with the docs index in ceo/INDEX.md. Follow PIPELINE-REVIEW.md. If the audit files don't exist yet, fall back to /api/health, /api/stale and /api/progress plus LIVE-FACTS.
2. Act only on critical findings, or on warnings that persisted across two audits. Confirm with the raw evidence before changing anything. Choose the smallest reversible fix: disable a duplicate cron line with a comment rather than deleting it, stop one duplicate process, or add a guard. Back up first. Change at most one pipeline per hour unless there's an emergency. Verify the previous hour's change against the new audit, and roll it back if things got worse. Dashboard glass changes follow KEEP-GLASS.md (aqua-press files only, with a `?v=` bump). A bake is allowed only when a fix needs one; follow BAKE-POLICY and record Jon's standing OK in BAKE-APPROVAL.md. Never flash the visor unless Jon has typed "flash it". Never delete data. Don't wake other agents or send Slack or email. Don't unpause the other BrickNet routines. If something needs more than a couple of commands, hand it to one background worker with this same method.
3. Append a short dated entry to GROKBOT-HOURLY.md on the drop: what you checked, the findings, what you changed, and the rollback command.
4. Tell Jon only when something was fixed, broke, or needs his decision, in a few plain sentences with evidence. Between 10 PM and 6 AM MT, stay quiet except for emergencies: dashboard down, a runaway spawn, data loss, a live mesh shrinking a lot or failing mesh QA, or the disk filling up. Put the overnight summary in the first message after 6 AM. Send nothing if nothing needed attention.

### 15. Remind Factry NPU meter when home
Remind Jon (one short message) that he said he'd fix Factry NPU Gemma token metering when he got home: add a usage log after generate() in C:\Kitchen\models\npu\npu_gemma_server.py, then factry_ctl restart-npu. Context is in ceo/TOKEN-USAGE-AUDIT-20261005.md. After sending the reminder, delete this routine so it only fires once.
(Status at retirement: never fired. Whether the NPU metering fix was done is unknown; carried as an open item.)

### 16. Check Cetus 08:45 hold (Sat 10/31)
Ask Keep (id 1adacc69-0450-47b0-b332-21c03dd467da) to read CETUS-STATUS read-only and confirm the 08:45 MT daytime Cetus block was held or skipped, not started, under STOP-STATE entry cetus-daytime-20261031 (which expires 21:59, so tonight's 22:00 block still runs). Tell Jon only if the block started or the status is unclear; stay quiet if it was held as planned.
