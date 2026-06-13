# Dynamic Workflows For Neko Core

Status: active
Last updated: 2026-06-13

Claude Code dynamic workflows let Claude write a small JavaScript harness that
coordinates subagents for the current task. Use them when the coordination is
the hard part: fan-out, independent verification, hypothesis testing, ranking,
or repeated loops with a stop condition.

## When To Use

Good fits for this repo:

- MTP root-cause investigation: split logs, build scripts, llama.cpp issues,
  and Docker integration into separate evidence lanes.
- Public-test error-structure analysis: one agent per disagreement, skeptical
  verifier per finding, synthesis only after the barrier.
- Rule mining: inspect recent Claude/Codex sessions and propose concise
  `CLAUDE.md` or skill updates.
- Patch review: writer/reviewer pattern with a fresh context reviewing the diff.
- Trace triage at scale: classify fallback reasons and route only the risky
  items to deeper inspection.

Poor fits:

- one-file docs edits;
- narrow test fixes;
- tasks where a normal subagent or `rg` search gives the answer;
- anything that would spend RunPod/GPU credits without explicit owner sign-off.

## Patterns To Ask For

- `fan-out-and-synthesize`: split many independent items, then merge structured
  results.
- `adversarial verification`: have a separate verifier try to disprove each
  claim.
- `generate-and-filter`: create candidate approaches, then apply a rubric.
- `tournament`: compare alternative approaches pairwise when absolute scoring
  is noisy.
- `loop until done`: continue until a deterministic stop condition holds.
- `quarantine`: agents reading untrusted text can report findings but cannot
  write files, spend money, or call external services.

## Neko Core Workflow Prompt

```text
Use a quick dynamic workflow for this Neko Core task.

Read AGENTS.md, CLAUDE.md, docs/claude-code/README.md, and the specific note I
name below. Keep the final Docker contract offline: /data -> /output/pred.csv.
No hard-coded qids, public answers, leaderboard hacks, secrets, Docker push, or
RunPod spend.

Task: <task>
Evidence files: <files or trace dirs>

Use:
- one explorer for local code/config;
- one explorer for external docs if needed;
- one skeptical verifier to challenge the proposed conclusion;
- a final synthesizer that separates measured facts from hypotheses.

Budget: <token/time budget>.
Stop condition: <test/log/check that proves done>.
Return changed files, commands run, and unresolved risks.
```

## MTP-Specific Workflow Prompt

```text
Use a dynamic workflow to prepare the next MTP measurement.

Do not launch or terminate RunPod unless I explicitly say so in this session.
Do not modify solver prompts. MTP is a runtime/provider speed lever.

Agents:
1. llama.cpp agent: inspect current upstream flags and known MTP/server issues.
2. repo agent: inspect Neko local_server provider and Docker entrypoint.
3. script agent: review scripts/gpu/run_mtp_server.sh for restart safety,
   full logging, KV f16, and no secret leakage.
4. verifier: try to find a reason the measurement would be invalid.

Output:
- exact next command sequence;
- files to pull from the pod;
- criteria for "MTP wins";
- criteria for stopping and terminating the pod.
```

## Budget Rule

Dynamic workflows often use more tokens than a normal session. Use them for
complex, high-value tasks where separate contexts reduce self-preferential bias,
agentic laziness, or goal drift. For routine edits, use the normal
explore-plan-implement-verify loop.
