# Real-time / current-law RAG — research + honest framing (2026-06-15)

Owner flagged this as the **next research problem**: can Neko Core get *current/real-time* VN-law &
admin data (many laws changed in 2025: 2-tier government from 1/7/2025, 63→34 provinces, mergers) so
the knowledge cluster stops losing points? This note separates what's possible from what isn't, and
where this lever actually belongs.

## The hard constraint first — "real-time" is IMPOSSIBLE in the contest container
The contest runtime is **offline & self-contained** (no network at inference). So *real-time*
retrieval at answer time **cannot exist** in the submitted image. The most achievable thing for the
contest is **"current-as-of-BUILD-time"**: rebuild a baked corpus from a fresh source snapshot right
before each submission. Calling that "real-time" would be wrong — it's a periodically-refreshed
snapshot. Do not promise real-time for the contest.

## New insight — the prior RAG test used a STALE corpus
The earlier "targeted RAG = dead" runs used `data/rag/legal_corpus.jsonl` built from an OLDER snapshot
(`YuITC/Vietnamese-Legal-Documents`) that largely PRE-dates the 2025 admin reform → it literally could
not contain the 2-tier-government / 34-province / Gia Lai-135-communes facts. So that test under-rated
the *knowledge* axis. Fresh sources now exist that DO capture the current state:
- **`undertheseanlp/UTS_VLC` (2026 split)** — a *verified in-force snapshot*, de-duplicated and
  validated against the official `vbpl.vn`. Best candidate for a "current" corpus.
- `vohuutridung/vietnamese-legal-documents` (~518k docs from thuvienphapluat.vn), `th1nhng0/…` &
  `doanhieung/vbpl` (from vbpl.vn).
- Official: Vietnam relaunched the **National Database on Legal Documents at vbpl.vn (23/4/2026)** —
  authoritative, but datasets are snapshots, "effect status reflects crawl time, not a live mirror."

## BUT — refreshing the corpus does NOT by itself fix the contest score
Two independent problems; a fresh corpus only addresses #1:
1. **Knowledge present?** — a 2026-in-force rebuild WOULD contain the current facts (improvement over
   the stale corpus). ✓ fixable.
2. **Gating?** — `notes/rag-oracle-dev-2026-06-15.md` showed retrieval surfaces the right fact, but NO
   cheap CPU gate separates the ~1-3% beneficiary slice; loose/always-on RAG injects noise and nets
   flat/negative. ✗ still unsolved. **This is the real blocker, and a fresher corpus doesn't fix it.**

So: a corpus refresh is necessary-but-not-sufficient for contest gain. Without a precise gate it stays
net-neutral/negative. The only contest-viable knowledge lever remains the **gate-free SHORT
"current-VN-2025" prompt-context line** (option A) — which scales to a *few high-frequency facts*, not
a whole law corpus, and still needs ONE GPU A/B with a no-regression gate.

## Where real-time law RAG genuinely belongs — Neko Core as an Agentic CLI (network allowed)
Outside the contest, the offline constraint is gone, so real freshness is achievable:
- **Tool-based retrieval at answer time** (the real "real-time"): a retrieval tool hitting a live
  source — web search or the vbpl.vn portal — grounded into the prompt. (The Wiii parent project
  already has a web-search stack — SearXNG + Crawl4AI + Jina — that is exactly this pattern; see the
  Wiii memory `phase-35-web-search-sota`.)
- **Scheduled corpus rebuild** (near-real-time): standard RAG-freshness practice — periodic/incremental
  reindex, per-chunk `last_modified`/`source` metadata for filtering + citation, snapshot versioning.
  A cron rebuild from UTS_VLC/vbpl before use keeps it current without inference-time network.
- **OKF refreshable knowledge layer**: store the curated current-law facts as an OKF bundle (markdown
  + frontmatter incl. `timestamp`) that a scheduled job regenerates; the BM25 retriever consumes it.
  (`notes/okf-assessment-2026-06-15.md`).

## Recommendation / next-session plan
1. **Contest:** do NOT chase a "real-time law RAG" — impossible offline, and corpus-refresh alone is
   blocked by gating. The honest contest lever is option A (gate-free current-fact context), GPU-gated.
2. **If revisiting RAG for the contest at all:** the ONE untested combo is *fresh corpus (UTS_VLC 2026
   in-force) + a PRECISE gate*. Before any GPU spend, dev-validate a better gate offline (e.g. a tiny
   classifier or a 2-stage retrieve-then-verify-relevance score) on the cluster-A questions; only if a
   gate cleanly isolates the slice WITHOUT over-firing is a GPU A/B warranted. Prior evidence says this
   is hard — treat as low-probability.
3. **Agentic CLI (beyond contest):** real-time/current-law retrieval is a legitimate, valuable feature
   — build it via a retrieval TOOL (web/vbpl) or scheduled OKF/corpus rebuild. Document in the dev
   guide as the "live knowledge" capability. Network is allowed there.

## Sources
- vbpl.vn National Database relaunch (23/4/2026): vietnamplus.vn / vietnamlawmagazine.vn.
- Datasets: HF `undertheseanlp/UTS_VLC` (2026 in-force), `vohuutridung/…`, `th1nhng0/…`, `doanhieung/vbpl`.
- RAG freshness practice: apxml.com "Managing Knowledge Base Updates", ragaboutit.com "RAG Freshness
  Paradox", newline.co "How RAG Enables Real-Time Knowledge Updates".
