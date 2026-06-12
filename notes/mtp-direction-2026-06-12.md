# MTP (Multi-Token Prediction) — Vòng-2 Time lever (2026-06-12)

## What it is

A speculative-decoding scheme: the model drafts several future tokens in one pass, then the
**main model verifies them in parallel** and keeps only the accepted ones. Because the main
model is always the final arbiter, the output is **bit-identical to non-MTP greedy/sampled
decoding → ZERO accuracy loss.** It is purely a *speed* technique, orthogonal to quant
(which is the accuracy lever).

## Why it matters for us (Vòng-2 Time score = 10 pts)

- **1.4–2.2× faster** running GGUFs; **Gemma-4 QAT + MTP = 1.5–2.2×**. Real-world ~1.6×
  typical (draft acceptance ~0.70); 2.2× is best-case.
- Available for **26B-A4B** — the exact model we ship. No accuracy trade-off.
- Our 26B does 2000 private q in ~1.6 h → with MTP ~**0.7–1.1 h**. Free Time-score win.
- +~2 GB VRAM headroom.

## Engine support / how to run

- Merged into **llama.cpp on 2026-06-07** (PR ggml-org/llama.cpp#23398).
- CLI flags: `--spec-type draft-mtp --spec-draft-n-max N` (start N=2; try 1–6, hardware-dependent).
- Bench data: gemma-4-12b 52→162 tok/s on a B200 (0.70 draft acceptance); 31B ~24→40 tok/s (~1.64×).
- unsloth ships the MTP draft weights in the repos (an `MTP/` subfolder, e.g.
  `unsloth/gemma-4-26B-A4B-it-GGUF` → `MTP/...`). Confirm the exact draft file for 26B-A4B at run time.

## OPEN — must verify before adopting (honesty)

1. **Does `llama-cpp-python` (our binding) expose MTP/spec-decode?** The merge is in the
   llama.cpp C++ core; the Python wrapper must (a) be built after 2026-06-07 and (b) expose
   the draft-mtp speculative params via the `Llama(...)` constructor. If the binding does NOT
   expose it, options: (i) upgrade/patch llama-cpp-python, (ii) switch the runtime to the
   `local_server` provider driving the llama.cpp HTTP server (`llama-server --spec-type
   draft-mtp ...`) which definitely supports it, (iii) call the CLI. This is a real
   integration task, not free.
2. Confirm the MTP draft GGUF for 26B-A4B + the exact load path.
3. Measure the REAL speedup on our hardware (acceptance rate varies); 2.2× is best-case.

## Plan

- Orthogonal to quant: ship BOTH (e.g. Q6_K + MTP = more accurate *and* faster).
- Same-GPU-session test (after the quant run, before terminating the pod): download the
  26B-A4B MTP draft, run a timed generation WITH vs WITHOUT `--spec-type draft-mtp`, record
  tok/s + that outputs match. First via llama.cpp CLI/llama-bench (proves the GGUF+flags),
  then verify whether `llama-cpp-python` can drive it for the offline Docker.
- If the Python binding can't drive MTP, evaluate the `local_server` provider path (the
  harness already has a `local_server` provider) — llama-server supports the flags natively.

## Results
(to be filled after the same-session GPU test)
