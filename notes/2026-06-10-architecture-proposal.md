# Architecture Proposal — Non-Overfit, Multilingual, Calibrated

Date: 2026-06-10
Status: PROPOSAL — ready to execute
Inputs: [baseline diagnosis](2026-06-10-baseline-85.53-diagnosis.md) + overfit/multilingual
audit (22 findings) + Claude Code source study + SOTA MCQ knowledge.

> Goal restated by the team: win on the **2000-question multilingual** private test
> (Accuracy 80pts, time 10pts, idea 10pts). The current 85.53 on 463 VI questions is
> **propped up by Vietnamese-specific heuristics and 463-specific adjudicators** that
> will not transfer — and we can't even see our errors because confidence is fake.
> **Do not overfit. The model reasons; the harness orchestrates, measures, and
> escalates only when uncertain.**

---

## 1. Seven design principles

1. **Model-first, heuristic-minimal.** Gemma-4 26B is the engine. Heuristics may only
   add *robust, language-agnostic* signal; they must **never overwrite the model with
   a hard-coded answer**. (Kills the whole overfit class.)
2. **Language-agnostic by default.** No per-language keyword routing. **Keep
   diacritics** (the model reads them natively; stripping only fed the broken router).
   One generic prompt that works in VI/EN/KO/ZH/… and answers in the question's frame.
3. **Reasoning enabled.** Allow chain-of-thought (raise `max_tokens`, drop
   "no explanation / one letter"), then **extract the letter** from the reasoned answer
   (`normalize_answer` already parses `ANSWER: X`). *Single biggest accuracy lever.*
4. **Real confidence via self-consistency.** Sample k reasoned answers (and/or diverse
   prompt framings); **confidence = agreement fraction**, not a hard-coded constant.
   This both raises accuracy (majority vote) and finally makes risk-review meaningful.
5. **Independent challenge, not self-confirmation.** When uncertain, escalate to a
   **different model** (Qwen3.5-8B, allowed) as challenger/judge, or a re-derive-from-
   scratch pass — never the same-model answer-only echo that inflates 0.88.
6. **Tiered, budget-aware compute.** Easy/high-agreement items → one cheap pass.
   Uncertain items → escalate. Respects the 10pt time score: spend tokens only where
   they change the answer. (Accuracy 80 ≫ time 10, but don't be needlessly slow.)
7. **Modular, contract-based (Claude Code lesson).** Replace god functions with small
   modules that each have a typed contract, config-driven. New language/question-type =
   config or one focused module, **never** edits across unrelated layers.

## 2. Why diacritic-stripping & keyword routing must go (the user's question)

The model is sent **raw, accented** text and understands it. `normalize_text` strips
diacritics **only** for an internal keyword classifier — a pre-LLM technique. But VI
tone marks are meaning-bearing, so `tỉnh/tính/tình/tinh → "tinh"` collide, and the calc
marker fires on provinces/feelings; on **KO/ZH the stripping is a no-op and every
`[a-z0-9]` heuristic returns nothing**, so CJK items get no routing at all. The fix is
not "better boundaries" — it's to **stop depending on lexical keyword routing** and use
language-neutral structural signals + the model's own reasoning.

## 3. Target pipeline

```
load (CSV/JSON, per-row letters)
  → profile  [LANGUAGE-NEUTRAL structural signals only:
               #choices, has_digits/math-symbols, context-block length, script]
  → solve    [CoT reasoning, ONE generic multilingual prompt, letter extracted]
  → self-consistency: k samples → majority vote → confidence = agreement
  → IF agreement < τ (uncertain):
       escalate → cross-model challenger (Qwen3.5-8B) OR +samples OR focused re-read
  → calibrated confidence attached
  → export pred.csv (qid,answer)
  → (dev only) trace + risk review  ← now meaningful, confidence is real
```

Easy items cost 1× (or k cheap shots); only the uncertain tail pays for escalation.

## 4. DELETE (overfit removal — asymmetric downside, ~0 private value)

| Remove | File | Why |
|---|---|---|
| 7 bespoke formula solvers + decision rule | `calculation.py` | Reverse-engineered from single public items; can grab the wrong number and **silently override a correct model answer**. Replaced by CoT (model does the math). |
| 6 hard-coded domain rules | `principles.py` | VI-only answer-string lookups; `refusal_for_harmful_anti_state_action` dangerously over-triggers on common civics phrasing. Zero transfer. |
| Magic-constant evidence vocab/boosts (`"500"+10`, stoning terms, `"dau tien"`) | `evidence.py` | Fingerprints of specific public questions; spurious or dead on private. |
| Strip-everything diacritics for routing | `normalize.py` / `classifier.py` | Word collisions + CJK no-op. Keep diacritics; route on structural signals. |
| `"Vietnamese"` hard-coded in prompts | `prompting.py` | Mis-frames EN/KO/ZH items. |

> ⚠️ **Trade-off to execute with eyes open:** these adjudicators were tuned to pass
> specific *public* items, so the **public score may dip a little** when removed — but
> they contribute ~0 on the unseen private 2000 and carry mis-fire risk. We optimize
> the **private** generalization (where the prize is), not the public vanity number.

## 5. KEEP (transfers well)

- Dev infra: trace / review / review-tasks / compare / checkpoint / session / events /
  manifest / submission validator — **excellent, keep**.
- Config-first profiles, policy gate, registries (agents/tools/commands), `--doctor`,
  `--check-submission`, `--yolo`. Strong governance; keep.
- Multi-label **feature extraction** already exists in `classifier.py` — keep it, just
  **stop collapsing to one `kind`** and make signals language-agnostic.
- `normalize_answer` letter parser — reuse for CoT extraction.
- Tournament/voting idea — **reframed** as self-consistency that yields real confidence.

## 6. Should we add subagents "để bàn luận"? (the user's question)

Two contexts, opposite answers:

- **Runtime container: NO.** Policy forbids subagents; must be self-contained. The
  legitimate in-runtime "multi-agent" is **multiple model calls**: self-consistency
  samples + a cross-model (Qwen) challenger. That is allowed and is exactly principle 4–5.
- **Development: YES, strongly.** Multi-agent workflows (like the ones used to produce
  this diagnosis) are the right tool to: audit traces, generate & adversarially critique
  prompt candidates, A/B strategies, review harness diffs. They improve config/prompts/
  tests and **never ship**. This is where "bàn luận" belongs.

## 7. Claude Code lessons applied

From the decompiled Claude Code source (`E:/Sach/Sua/test/claude_lo/claude-code`):

- **Layered loop** (`query.ts` low-level tool/stream loop vs `QueryEngine.ts` high-level
  orchestration vs `REPL.tsx` UI) → split Neko's `solve_problem` god function into a
  thin orchestrator + strategy modules + adjudicator, mirroring this separation.
- **Tools as self-contained contracts** (`src/tools/<Name>/` each with
  name/description/`inputSchema`/`call()`) → each Neko strategy & adjudicator becomes a
  small module with a typed contract, registered, config-selected.
- **Thinking captured as a first-class artifact** (`thinking_capture.ts`) → Neko
  currently *suppresses* reasoning; we should capture CoT into the trace (dev) and parse
  the letter out (runtime). Direct support for principle 3.
- **Structured context assembly** (`context.ts` builds the system prompt from parts) →
  build Neko prompts compositionally (task + options + answer-format), not as VI blobs.
- **Subagents for dev refactors** (RECORD.md: "4 rounds of parallel agents, 7 each" to
  fix 1341→294 type errors) → validates using dev-time multi-agent workflows.

## 8. Sequenced roadmap (for the executor — Fable 5)

Each phase: tests green before & after; re-run public sample + compare answer stability;
write a `notes/` entry. **Light, surgical refactor only where we're already changing
code** — not a big-bang rewrite first (avoids refactoring code we're about to replace).

- **Phase 0 — Safety net (small).** Add a tiny held-out **multilingual smoke set**
  (a few EN/KO/ZH/math items) + a local eval that checks the pipeline doesn't crash or
  mis-route on non-VI. Confirm `python -m unittest` green. Gives us a generalization
  signal we currently lack.
- **Phase 1 — Reasoning + real confidence (biggest lever).** Enable CoT (generic
  multilingual prompt, higher `max_tokens`, robust letter extraction) + self-consistency
  (k samples → vote → agreement-based confidence). Extract the new solve path into a
  clean `strategies/self_consistency.py` + `calibration.py` (surgical refactor here).
  Measure tokens/sec cost. *Expected: accuracy up, confidence finally informative.*
- **Phase 2 — Remove overfit / de-risk transfer.** Delete bespoke calc/principle/
  evidence rules; make routing language-agnostic; keep diacritics; language-neutral
  prompts. Verify public score (expect small dip, acceptable) + multilingual smoke
  (expect robustness up).
- **Phase 3 — Independent challenger + tiering.** Add Qwen3.5-8B cross-model challenger
  for low-agreement items; tier compute to stay inside the time budget.
- **Phase 4 — Full modular split.** Finish decomposing `solver.py`/`run.py` into
  `routing/ strategies/ adjudicate/ calibration.py risk.py` per Claude Code layering.
- Throughout: submit to the leaderboard at milestones (limited submissions — be
  deliberate), record results here.

## 9. Open trade-offs to measure (not assume)

- **CoT token budget vs 10pt time score.** CoT + k samples increases output tokens
  materially on 2000 questions; Gemma-4 26B Q4 throughput on contest hardware is
  unknown. Tiering (principle 6) is the lever; measure tokens/sec early in Phase 1.
- **k and τ** (samples, agreement threshold) — tune empirically, keep in `config`.
- **Cross-model judge cost** — only on the uncertain tail; measure its size first.
- **Public-score dip** from removing overfit adjudicators — acceptable if private
  generalization improves; confirm magnitude before final submission.
