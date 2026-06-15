# OKF (Google Open Knowledge Format) — fit + readiness assessment (2026-06-15)

Owner asked whether Google's newly-announced **Open Knowledge Format (OKF)** fits Neko Core and is
ready to use.

## What OKF actually is (verified from the spec + Google Cloud blog, 12/6/2026)
- A **vendor-neutral, open FORMAT** for representing organizational knowledge as a **directory of
  markdown files with YAML frontmatter**. v0.1, **draft / experimental**, "a starting point, not
  finished."
- **Required frontmatter:** only `type`. **Recommended:** `title`, `description`, `resource` (URI),
  `tags`, `timestamp`. Reserved files `index.md`, `log.md`. Body = standard markdown with
  conventional `# Schema` / `# Examples` / `# Citations` sections; cross-links via markdown links.
- **Purely an authoring/storage format** — the spec has **no retrieval, embedding, or runtime**
  guidance. It says how knowledge is *captured and exchanged*, not *consumed at inference time*.
- **Fully offline + vendor-neutral:** "just files" (git repo / tarball / mounted dir); no SDK, no
  account, no Google Cloud, no schema registry. License not stated in the spec page.
- Source: GoogleCloudPlatform/knowledge-catalog `okf/SPEC.md`; cloud.google.com/blog
  "how-the-open-knowledge-format-can-improve-data-sharing".

## Fit for Neko Core — three lenses

### 1. Contest runtime (offline MCQ) → NOT a fit, zero score impact
- OKF is a *knowledge-authoring format*, not a retrieval engine or inference technique → it cannot
  change Accuracy. The contest is closed-book MCQ; the model answers from parametric knowledge.
- Even for the RAG corpus path: our corpus is JSONL `{id,title,text}` consumed by an in-process BM25
  retriever. OKF (markdown + YAML frontmatter) is *functionally equivalent input* for BM25 — switching
  buys **no accuracy**, only adds a frontmatter parser to a runtime we keep intentionally minimal.
  And the RAG-gate path is already dev-disproven (`rag-oracle-dev-2026-06-15.md`).
- Time score: unaffected. Idea score: a passing "standards-aligned" mention is possible but marginal.
- **Verdict: do NOT adopt OKF in the contest image.** No benefit, and adopting an experimental v0.1
  standard under the 23/6 deadline is pure downside.

### 2. Neko Core as a reusable Agentic CLI (beyond the contest) → GOOD conceptual fit
- Neko Core is already config-first and offline-first; OKF's "just files, no SDK" philosophy matches.
- A future Neko Core **knowledge layer** could *consume* OKF bundles as its corpus (the BM25 retriever
  would just read OKF markdown bodies instead of JSONL `text`). This is the legitimate place OKF fits
  — documented as a forward-looking option in `docs/AGENTIC-CLI-DEVELOPER-GUIDE.md`, not built now.

### 3. Our own notes/memory → already ~OKF-shaped; no action
- The repo `notes/` are markdown; the agent memory files already use YAML frontmatter
  (`name`/`description`/`metadata`). We're already most of the way to OKF by convention. Formally
  migrating is low-value busywork under deadline. Skip.

## Readiness
- **As a format:** trivially ready (it's just markdown + YAML; no dependency). Adoptable any time.
- **As an ecosystem:** **NOT mature** — v0.1 draft, experimental, no stable/required tooling, spec
  explicitly expects breaking-ish evolution. Not something to build a contest deadline on.

## Recommendation
1. **Contest (now):** do nothing — OKF gives no Accuracy/Time/Idea edge and the deadline is 23/6.
2. **Future (agentic CLI):** add a short forward-looking note to the dev guide that Neko Core's
   knowledge layer is OKF-alignable (consume OKF bundles as the offline corpus). Low effort, honest,
   and a genuine standards-alignment talking point for the "reuse beyond contest" story.
3. Re-evaluate if/when OKF reaches ≥v1.0 with stable tooling.
