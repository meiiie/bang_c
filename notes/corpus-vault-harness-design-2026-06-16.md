# Disciplined current-fact corpus vault — design (2026-06-16)

## STATUS — Step 1 BUILT (2026-06-16): vault + compiler, byte-identical refactor
- `scripts/build_corpus_vault.py` (validates id/title/source/verified, dup-id fail, candidate-quarantine,
  near-dup report, `--check`, `--include-candidates`).
- `data/rag/vault/` authored: `README.md` (charter) + `_schema.md` + `vn-admin-2025/README.md` + 37
  atomic fact files (2 overview + 35 `provinces/`), each with full frontmatter.
- `data/rag/current_vn_2025.jsonl` regenerated FROM the vault → `--check` content-identical → rag-gated
  byte-unchanged. 254 tests green. The ship image is unaffected (it COPYs the compiled JSONL).
- NEXT = Step 2 expansion (author new authoritative facts batch-by-batch through the measurement loop)
  — see the expansion checklist in `vn-admin-2025/README.md`. Needs authoritative sourcing + a GPU
  gate-audit per batch.

## STATUS — Step 2 research round 1 (2026-06-16, web-sourced)
- **Merger map VERIFIED-COMPLETE.** Web-checked all 23 mergers in the active vault against Resolution
  202/2025/QH15 (luatvietnam + vietnam-briefing): ALL 23 correct, including the 6 three-way mergers
  (Phú Thọ, Ninh Bình, Lâm Đồng, HCMC, Cần Thơ, Vĩnh Long). The existing corpus is accurate; no fixes.
- **Administrative centres researched (23) → CANDIDATE** (`candidate/vn-admin-2025-centers/`). Several
  non-obvious (Lào Cai→Yên Bái, Bắc Ninh→Bắc Giang, Gia Lai→Bình Định, Tây Ninh→Long An, Đồng Tháp→Tiền
  Giang, An Giang→Kiên Giang) — exactly the current-facts exams ask. Source carried a "dự kiến" caveat
  → status:candidate until cross-verified against the FINAL NQ 202 (vbpl.vn). NOT shipped.
- **Temples/chùa (4 well-known) → CANDIDATE** (`candidate/vn-religion-temples/`). Honest: low-EV
  (knowledge-trivia, can't cover all temples, specific questions unlikely to match) — let the gate-audit
  + a probe run decide; expect ~no help.
- Active ship corpus UNCHANGED (37, 88.98 preserved); `candidate_corpus.jsonl` = 64 for measurement.
- NEXT: (a) verify the 23 centres vs final NQ 202 → promote the high-value ones; (b) gate-audit the
  candidate corpus (0-FP safety) before any promotion; (c) the real payoff is the 2000-private — the 463
  probe can only confirm safety, not help. The 93.74 gap stays mostly knowledge/reasoning-bound (NOT
  corpus-closable per the roadmap); corpus adds the verifiable current-fact slice only.

Owner's idea: grow the current-fact RAG corpus to cover MORE domains where the model errs, with a
**well-structured, documented harness** (vaults / per-folder + per-file .md docs) and WITHOUT
introducing false-positives ("không bị loạn"). This is a DESIGN note — think + reference before building.

## The unlock (why this is viable NOW, vs the old "low-probability" verdict)
`notes/realtime-law-rag-research-2026-06-15.md` rated corpus expansion low-probability because **"no
cheap gate isolates the beneficiary slice — loose RAG nets negative."** That blocker is now GONE: the
dense reranker gate (threshold 0.85 + reading-guard) is **leaderboard-proven** (88.34→88.98, 0
false-positives on the 463). So the precise gate the note said we lacked, we now have. Expansion is
the one accuracy lever with real headroom — but it lives or dies on DISCIPLINE, not volume.

## Two independent failure modes a corpus must avoid (both proven before)
1. **Stale / wrong facts** — the old `legal_corpus.jsonl` predated 2025 → couldn't answer current facts.
   The big law corpus also netted −2: noisy chunks + one wrong fact poisons.
2. **Over-firing** — forced-RAG-on-everything lost −5pp on civics; the gate fixes this, but only if the
   corpus stays in the slice the gate is tuned for (current-fact). Adding off-distribution domains can
   pull the gate's score distribution and re-introduce false-positives.

→ The harness must make BOTH hard to get wrong by construction.

## Architecture — a markdown vault compiled to the retriever JSONL
Source-of-truth = human-authored markdown (frontmatter + body), organized by domain; a build step
compiles it to the `{id,title,text}` JSONL the BM25+reranker actually load. Markdown is reviewable,
diff-able, citable; the JSONL is a generated artifact (never hand-edited).

```
data/rag/
  vault/                              # SOURCE-OF-TRUTH (human-authored markdown)
    README.md                         # charter: principles, source policy, the gate, build cmd, status
    _schema.md                        # frontmatter schema + chunk rules (atomic, sourced, verified)
    vn-admin-2025/                    # DOMAIN folder (active, proven slice)
      README.md                       # scope · authority · last-verified · coverage checklist
      two-tier-government.md
      reform-overview.md
      provinces/                      # sub-vault: one file per province (atomic, isolatable)
        gia-lai.md
        ha-noi.md
        ...
    candidate/                        # QUARANTINE — NOT compiled into the ship corpus until measured
      vn-civics-sgk/
        README.md
        ...
  current_vn_2025.jsonl               # COMPILED active corpus (the ship artifact; generated)
  candidate_corpus.jsonl             # COMPILED active+candidate (for measurement runs only)
scripts/
  build_corpus_vault.py               # vault/**.md -> jsonl + a build report (counts, sources, dups)
```

### Per-fact file (frontmatter + atomic body)
```markdown
---
id: vn2025-gialai-xa               # stable, unique (build fails on dup)
title: Tỉnh Gia Lai sau sáp nhập có 135 đơn vị cấp xã
domain: vn-admin-2025
source: "Nghị quyết 202/2025/QH15 (12/6/2025); vbpl.vn"
source_authority: official         # official | gazette | secondary  (build warns on secondary)
verified: 2026-06-15               # current-as-of-build date
tags: [gia-lai, commune-count, merger-2025]
status: active                     # active -> ship corpus ; candidate -> quarantine only
---
Sau sắp xếp đơn vị hành chính năm 2025 (hợp nhất Gia Lai và Bình Định), tỉnh Gia Lai có 135 đơn vị
hành chính cấp xã. (Một fact / file — sai một file thì xoá đúng một file, không lan.)
```

### `build_corpus_vault.py` (the disciplined compiler)
1. Walk `vault/**/*.md` (skip `candidate/` for the ship build; include it for the candidate build).
2. Parse frontmatter; **REJECT** any chunk missing `id`/`title`/`source`/`verified`; **FAIL** on dup `id`.
3. Warn on `source_authority: secondary`; refuse `status: active` without an official/gazette source.
4. Emit `{id,title,text}` (+ keep `source`/`verified` as sidecar metadata for citation/audit).
5. Print a report: chunks per domain, sources histogram, any near-duplicate texts (so the corpus stays
   atomic + non-redundant — redundant chunks crowd retrieval, the law-corpus failure mode).

## The discipline that prevents "loạn" (no-FP by construction)
- **Dense gate stays the guard** (reranker ≥0.85 + reading-guard) — proven 0-FP. The corpus must not
  drift the gate's score distribution; the audit below checks that every time.
- **Atomic + sourced + verified** — one fact per file, each citing an authoritative source + date. A
  wrong fact is isolated and removable; an unsourced fact can't ship.
- **Candidate-quarantine** — a NEW domain lands in `candidate/`, is compiled into `candidate_corpus.jsonl`
  ONLY, and is measured before any promotion. Nothing reaches the ship corpus unmeasured.
- **current-as-of-BUILD, not real-time** — offline container; the corpus is a dated snapshot, rebuilt
  before each submission. Do not call it real-time.

## The measurement loop (gate on this BEFORE promoting any domain — reuse what we built)
1. Author the domain in `candidate/`, compile `candidate_corpus.jsonl`.
2. **Gate-audit** (`Temp/pod_mtp/run_gateaudit.sh` pattern): score the reranker over the 463 probe (and
   a held-out current-fact set) with the candidate corpus → confirm the gate still fires ONLY on genuine
   current-fact, **0 new false-positives at 0.85**, and the score gap (genuine ≫ junk) stays wide.
3. **`scripts/analyze_errors.py`** vs the locked baseline → confirm changed answers are ONLY genuine
   current-fact fixes, **no regression** on other clusters.
4. Promote (`status: active`) + recompile the ship corpus ONLY if both are clean. Else keep in
   candidate + log the honest negative.

## Domain priority (from `notes/public463-error-audit` domain map — 34 errors)
- **EXPAND first (proven-safe slice): VN admin / current-policy 2025** (7/34 errors; the active domain).
  Add: per-province commune/ward counts, the 23 merged + 11 kept detail, district-abolition procedures,
  ward/commune renames, the key Nghị quyết (202/2025/QH15, 1656/NQ-UBTVQH15...), citizen-procedure
  changes (where to file paperwork). This is where the 2000-private (more current-fact qs) pays off.
- **CANDIDATE (measure, higher risk): VN civics/SGK facts** (10/34). Forced-RAG lost −5pp here; the
  dense gate MIGHT isolate a sub-slice, but civics knowledge is broad/parametric. Quarantine + measure;
  expect it to fail the 0-FP gate and stay out.
- **DO NOT corpus**: reading (answer is in the passage — reading-guard already blocks), quant (reasoning
  not knowledge), religion/philosophy trivia (unverifiable, broad → poisons).

## EV + honest bounds
- Helps ONLY current-fact questions the gate catches. 463 had 6 (3 fixed → +0.64). The 2000-private is
  multilingual + likely has MORE current-fact qs → bounded but real headroom there (the actual target).
- Hard ceiling unchanged: the ~15 knowledge-trivia errors are NOT corpus-fixable; a general corpus HURTS.
  The win is NARROW + GATED, never "more facts = more points."
- Risk: a single wrong/ambiguous fact poisons a question. Mitigated by source-discipline + atomic
  chunks + the candidate-quarantine + the 0-FP gate-audit. **Grow slowly, measure each step.**

## Companion cheap lever — cluster-targeted prompts (separate from the corpus)
Prompt-only (k=1, 0 Time cost), measured on a labeled dev set:
- **Negative questions** (`has_negative` already detected) — inject one line into `build_reasoning_prompt`
  when present: "Câu hỏi này hỏi phương án KHÔNG đúng / SAI / NGOẠI TRỪ — chọn phương án không thoả mãn."
- **Most-exact short-factual** — a "chọn phương án CHÍNH XÁC/ĐẦY ĐỦ NHẤT, không chỉ hợp lý" instruction,
  gated on the short-factual slice. Harder: no clean feature, and it touches the default path — must be
  cluster-gated + measured for no-regression (the labeled-negatives dev set is the gating need).
Both: config-gated, default OFF, dev-measured before any contest use. Lower EV than the corpus but free.

## Recommendation / sequencing
1. Build `scripts/build_corpus_vault.py` + migrate the existing 37 chunks into `vault/vn-admin-2025/`
   with full frontmatter + per-folder README.md (no behaviour change — same compiled JSONL; pure
   refactor to the disciplined structure). Verify the rag-gated run is byte-identical.
2. EXPAND `vn-admin-2025` with more authoritative 2025 facts, one domain-batch at a time, each gated on
   the measurement loop (gate-audit 0-FP + analyze_errors no-regression).
3. Prompt-targeting as a parallel cheap experiment (needs a labeled-negatives dev set first).
Keep the locked 88.34 image + the rag-gated 88.98 as the safe fallbacks throughout.
