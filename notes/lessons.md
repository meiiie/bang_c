# Lessons (append-only)

Durable lessons learned while building Neko Core. Newest on top.

## 2026-06-10

- **Verify feedback against code + real data before acting.** A teammate's 6-point
  critique was ~80% right, but: one example set was claimed stale (it wasn't), one
  ordering detail was wrong (calc is prioritized *before* many_choice), and the true
  root cause of the routing bug was mis-framed (it's diacritic collision, not
  substring-vs-token). Trusting it verbatim would have produced the wrong fix.
- **Fake confidence hides everything.** Hard-coded per-path confidence made ~57 wrong
  answers invisible (79.5% sat at ≥0.88). Before chasing accuracy, build a *real*
  uncertainty signal (self-consistency / cross-model disagreement). You can't fix
  errors you can't see.
- **Diacritics are meaning-bearing in Vietnamese.** Stripping them for keyword
  matching collapses `tỉnh/tính/tinh`. The model never needed stripping — only the
  legacy router did. Prefer language-agnostic structural signals over keyword routing.
- **Suppressing reasoning then patching with hand-coded math is backwards.** Letter-
  only prompts (`no explanation`) hurt reasoning items; the ~7 bespoke calculation
  solvers are a symptom-patch that overfits the 463 public questions.
- **Overfit = transfer risk.** Anything tuned to 463 public items or to Vietnamese
  specifically is a liability on the 2000-question multilingual private test.
- **Notebook discipline.** Investigations live in `notes/` with file:line evidence,
  one dated file per topic; `lessons.md` captures the durable takeaways.
