# Guardrail fix and accuracy research frame - 2026-06-13

Status: active handoff note for Neko Core teammates.

Owner context: HackAIthon 2026 Bang C, Neko Core, local-first Gemma-4
26B-A4B QAT Q4_0 GGUF runtime.

## Why this note exists

Claude/Codex sessions had notes and scripts that assumed a development-workflow
guardrail already existed: `--allow-development-workflow` or
`HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1`. The current `HEAD` did not actually
enforce it. That mismatch was dangerous because measured-dead development
workflows such as `router`, `tir`, `reading`, `rag`, `tiered-consistency`,
`tournament`, and `verify-all` could still be launched non-dry-run by accident.

This note records the fix, what the guardrail means, what remains risky, and the
research frame for trying to break past the current 88.55 band without public
test hardcoding.

## What was fixed

Files changed by this guardrail patch:

- `src/hackaithon_c/run.py`
- `tests/test_contract.py`

Behavior added:

- CLI flag: `--allow-development-workflow`
- Environment opt-in: `HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1`
- Non-dry-run workflows with `phase=development` now fail closed unless the flag
  or env opt-in is present.
- Direct CLI selection of a development-only strategy also fails closed unless
  explicitly allowed. Example: `--strategy tiered`.
- Dry-run development workflows remain available for contract smoke tests.
- Runtime workflows remain unaffected: `contest-auto`, `contest-strict`,
  `self-consistency`.

Manual gate matrix after the patch:

```text
--workflow router                                      => EXIT=2
--workflow tiered-consistency                          => EXIT=2
--strategy tiered                                      => EXIT=2
--workflow router --allow-development-workflow         => EXIT=0
HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1 --workflow reading  => EXIT=0
--workflow router --dry-run                            => EXIT=0
--workflow quick-dry-run                               => EXIT=0
```

Verification after the patch:

```text
targeted guardrail tests: OK
python -m compileall -q src tests scripts: PASS
python -m hackaithon_c.run --policy: PASS
git diff --check: PASS, CRLF warnings only
python -m unittest discover -s tests -v: 226 tests OK
```

## What "guardrail" means here

A guardrail is an enforced boundary, not advice in a note.

For this repository the important guardrail layers are:

1. Runtime contract guardrail
   - Final Docker reads `/data`.
   - Final Docker writes `/output/pred.csv`.
   - Output columns are exactly `qid,answer`.
   - Runtime must not depend on web browsing, Claude Code, notebooks,
     databases, hidden local files, or external APIs.

2. Development-workflow guardrail
   - Development candidates may exist in config and solver code.
   - They must not run model inference by accident.
   - Non-dry-run dev workflows require explicit experiment opt-in.
   - Dry-run contract smoke remains allowed.

3. Accuracy-promotion guardrail
   - No public-test qids, answer files, leaderboard observations, or
     private-test assumptions in `src/`, `configs/`, or tests.
   - Any accuracy change needs a hypothesis, a generalization argument, a
     paired measurement, and a written stop rule.
   - A PASS on proxy evidence means "ready for owner review", not automatic
     submission.

4. Spend/publish guardrail
   - RunPod/GPU spend, Docker push, and leaderboard submission require owner
     sign-off in the current session.

Current judgment: the development-workflow guardrail is now much stronger. It is
not a full formal security sandbox. It does not stop someone from calling
`solve_problem(..., strategy="router")` directly in a custom Python script, and
it does not replace owner sign-off for GPU/Docker/leaderboard actions. It does
close the ordinary CLI/script path used by this harness.

## Current measured state

Current baseline:

- Contest/default path: Gemma-4 26B-A4B QAT Q4_0, self-consistency CoT, `k=1`,
  `reasoning_max_tokens=2048`, safety lever on.
- Public leaderboard band: about 88.55.
- Public proxy agreement has varied run-to-run by about 0.6pp in measured notes;
  do not treat one public-proxy run as exact truth.

Measured dead or negative levers:

- Router/TIR on real 463 proxy: -9.29pp versus self-consistency.
- Bespoke deterministic public-derived rules: removed as overfit.
- Majority vote / k>1 diverse self-consistency: wash; errors appear systematic.
- Q6/Q8 precision upgrades: tied to worse and slower than QAT Q4_0.
- Dense 31B: too slow / too much VRAM for final scoring.
- Qwen standalone or naive adjudicator: not justified by measurements.
- Reading/RAG/few-shot/tiered: measured flat/negative or not worth promoting.

MTP:

- MTP is a speed lever, not an accuracy lever.
- Real MTP benchmark on RTX 3090 found best around 1.37x, below the local 1.4x
  gate, with MoE caveats matching upstream warnings.
- The next useful GPU check is Docker smoke, not another tok/s-only benchmark:
  build/run the actual image offline, prove `/data -> /output/pred.csv`, and
  prove fallback still produces a valid output when `llama-server` fails.

## Why competitors may reach 89-92

We cannot know their internals, so treat this as hypothesis only.

Plausible reasons:

- They may be using a stronger final model/runtime configuration within rules,
  or accepting slower inference for more accuracy.
- They may have better answer-selection, confidence, or verifier harnesses that
  recover correct candidates from multiple samples instead of plain majority
  vote.
- They may have stronger domain knowledge or curated offline corpora, especially
  Vietnamese legal/admin/local facts.
- They may have more robust multiple-choice debiasing against option-order and
  symbol-binding failures.
- Some leaderboard movement may be run-to-run variance or public-test luck.
- Some approaches could be overfit to public test; do not imitate that without
  generalization proof.

The useful lesson is not "copy a hack"; it is "build a better eval-driven
candidate-selection harness."

## Research signals checked on 2026-06-13

Primary/source links:

- OpenAI eval guidance: https://developers.openai.com/api/docs/guides/evals
- Anthropic eval harness framing: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic large-codebase Claude Code practice:
  https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start
- EleutherAI lm-evaluation-harness:
  https://github.com/EleutherAI/lm-evaluation-harness
- Self-consistency paper:
  https://arxiv.org/abs/2203.11171
- CISC, Confidence Improves Self-Consistency:
  https://arxiv.org/abs/2502.06233
- RISC, Boosting Self-Consistency with Ranking:
  https://arxiv.org/html/2606.05054v1
- Sample, Scrutinize and Scale:
  https://openreview.net/forum?id=wl3eI4wiE5
- Multiple-choice symbol binding:
  https://arxiv.org/abs/2210.12353
- Vietnamese MCSB:
  https://arxiv.org/html/2310.12059v5
- Selection-bias / permutation-aware GRPO:
  https://arxiv.org/html/2603.21016v2
- Gemma 4 MTP overview:
  https://ai.google.dev/gemma/docs/mtp/overview
- Google speculative decoding retrospective:
  https://research.google/blog/looking-back-at-speculative-decoding/
- llama.cpp Gemma 4 MTP PR:
  https://github.com/ggml-org/llama.cpp/pull/23398

Research takeaways:

1. The harness matters as much as the model.
   - Anthropic frames an eval harness as the system that runs tasks, records
     traces, grades outputs, and aggregates results.
   - For Neko Core this means every new idea must become config, tests, traces,
     and measured artifacts, not just a prompt tweak.

2. Plain majority self-consistency is not the end of the road.
   - RISC (2026) shows that answer selection can be treated as a ranking problem
     over candidate answers using features such as frequency, semantic
     centrality, and reasoning-trace consistency.
   - This is highly relevant because our k>1 majority vote was a wash. The open
     question is whether correct answers appear in the candidate pool but
     majority voting fails to select them.

3. Confidence-weighted self-consistency is a plausible low-scope experiment.
   - CISC (2025) reports that within-question confidence can make
     self-consistency more efficient than plain majority voting.
   - For local GGUF, this requires checking what confidence signals are
     realistically available: answer-token logprobs, a one-token self-check,
     or a separate cheap verifier prompt.

4. Verification must compare candidates, not only ask "am I right?"
   - Sample/Scrutinize/Scale reports that comparing across responses gives
     useful error signals, and that chains of thought are useful for reasoning
     but harder to verify.
   - For Neko Core, candidate verification should likely use concise answer
     rationales or option-level evidence, not long free-form CoT transcripts.

5. Multiple-choice bias is a real failure class.
   - MCSB work argues that MCQ models must bind symbols A/B/C/D to option
     content; selection-bias papers show option order and label symbols can
     change decisions.
   - Neko Core already has some permutation/tiered work, but it was not enough
     as implemented. A better experiment should first measure instability and
     oracle headroom, not blindly add permutations everywhere.

6. MTP should stay in the Time lane.
   - Google states Gemma 4 MTP keeps quality while speeding decoding, but also
     warns MoE 26B A4B may have weak speedups at batch size 1 or hardware
     without enough parallelism.
   - Local measurement matched that caveat: real but modest speedup.

## Candidate research program to break 88.55 safely

The next phase should be a research harness, not immediate solver edits.

### Phase 0 - freeze and protect

- Keep `self-consistency` as the default contest path.
- Keep development-workflow guardrail active.
- Do not submit or push Docker without owner sign-off.
- Do not revive measured-dead levers unless there is a new, written hypothesis.

### Phase 1 - build an oracle/headroom analyzer

Goal: answer "does a better answer appear among samples?"

For a small measured run on a labeled external/proxy set, collect per-question:

- baseline answer;
- N sampled answers at different seeds/temperatures;
- normalized answer letters;
- optional concise rationales;
- answer frequency;
- option-order sensitivity;
- confidence/logprob/self-check signals if available.

Then compute:

- baseline accuracy;
- majority-vote accuracy;
- oracle pass@N accuracy;
- per-bucket oracle headroom;
- percentage where correct answer exists but majority fails.

Promotion rule:

- If oracle headroom is near zero, stop; the problem is knowledge/model capacity.
- If oracle headroom is real, move to ranker/verifier research.

### Phase 2 - train-free ranker/verifier selection

Candidate methods, in order:

1. CISC-style confidence weighting.
   - Try answer-token logprob if llama-cpp exposes it reliably.
   - If not, try a one-token self-check prompt per candidate.

2. RISC-style lightweight answer ranker.
   - Use only general features: frequency, semantic centrality, trace
     consistency, confidence/self-check, option-order stability.
   - Train/tune only on non-public labeled sets or clearly separated synthetic
     data. Public 463 can be a final selection signal only, not training data.

3. Pairwise candidate comparison.
   - For low-confidence or disagreement cases only.
   - Compare two candidate answers/rationales and ask which is better grounded.
   - Must be measured because naive self-verification can backfire.

### Phase 3 - MCQ bias probe

Goal: determine whether option-order bias is costing real points.

Run cyclic permutations on a small labeled external/proxy set:

- keep option content identical;
- map predicted semantic answer back to original label;
- measure stability, wins, and false flips.

Promotion rule:

- Only use permutation debiasing if it improves paired accuracy and does not
  create many false flips. Avoid blanket expensive permutation if headroom is
  small.

### Phase 4 - offline knowledge augmentation only if targeted

RAG did not win broadly. If revisiting knowledge:

- use a small, curated, offline corpus;
- target only a clearly measured failure bucket;
- require retrieval evidence to be fallible, not ground truth;
- never inject public-test facts or qids.

### Phase 5 - one paired GPU run, then decide

Any promising candidate must run paired with the current baseline on the same
pod/model/config.

Required artifacts:

- full command line;
- git commit;
- config;
- `pred.csv`;
- trace summaries;
- changed-answer audit;
- no-regression gate;
- note in `notes/`.

## Proposed long-running Codex goal prompt

```text
Goal: Find a generalizable path beyond the current 88.55 band for Neko Core
without hardcoding public-test answers, qids, leaderboard observations, or
private-test assumptions.

Read first:
- AGENTS.md
- notes/2026-06-13-guardrail-fix-and-accuracy-research-frame.md
- notes/session-2026-06-12.md
- notes/router-tir-measured-2026-06-13.md
- notes/mtp-measured-2026-06-13.md
- notes/lessons.md

Non-negotiable:
- Keep final Docker offline: /data -> /output/pred.csv.
- Default runtime remains self-consistency until a measured gate passes.
- Do not revive measured-dead levers by default: router/TIR, public-derived
  deterministic rules, maj@k majority voting, quant swaps, dense 31B, naive
  Qwen, broad reading/RAG.
- No RunPod/GPU spend, Docker push, or leaderboard submit without owner sign-off.
- Non-dry-run development workflows require --allow-development-workflow or
  HACKC_ALLOW_DEVELOPMENT_WORKFLOW=1.

Research loop:
1. State one hypothesis and why it generalizes.
2. Build or reuse an eval artifact that does not train on public answers.
3. Measure baseline vs candidate with paired commands.
4. Record oracle headroom, wins, losses, and false flips.
5. Only then make a surgical code/config change.
6. Run compileall, policy, targeted tests, full unittest, and dry-run contract.
7. Write the result to notes/. If evidence is weak, stop and report no
   promotion.

Priority hypotheses:
- Oracle/headroom analyzer for sampled candidate pools.
- CISC-style confidence weighting if logprob/self-check signals are available.
- RISC-style lightweight ranker over candidate-set features.
- MCQ option-order/symbol-binding stability probe.
- Narrow offline knowledge augmentation only after a measured bucket says it is
  needed.
```

## Immediate next tasks

1. Keep this note as the handoff entry for the guardrail fix and research plan.
2. Add or update any team prompt to reference this note before future accuracy
   research.
3. Decide whether to run a small no-GPU oracle/headroom analysis first, or to
   spend a controlled GPU run to collect candidate pools on an external/proxy
   set.
4. Separately, after owner sign-off, run the Docker GPU smoke for Vong 2
   contract risk.
