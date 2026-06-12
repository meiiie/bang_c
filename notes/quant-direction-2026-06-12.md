# Higher-precision quantization — active accuracy lever (2026-06-12)

## Why this, and why now

Every cheap/obvious accuracy lever is measured-dead: TIR, reading-grounding, RAG, **maj@k
diverse voting (WASH — Gemma's errors are systematic, voting confirms the same wrong
answer)**, few-shot, tiered, UD-Q4_K_XL, Qwen-9B standalone, dense-31B (Time). The one
untried direction with a real mechanism is **the quantization of the weights themselves.**

We ship **Gemma-4-26B-A4B at Q4_0** (QAT). Measured/known gap:
- 26B-Q4 ~82.7% vs full-precision ~86.7% on a math proxy = **−4pp**, concentrated in the
  quantitative bucket (the headroom bucket).
- Independent research (`notes/research-97-cited-reports.md`): naive **4-bit costs ~10pp**
  on AIME, while **8-bit / FP8 is ~free** accuracy. UD-Q4_K_XL (another 4-bit) was slightly
  negative — so the fix is *more bits*, not a different 4-bit.

The model stays **Gemma-4-26B-A4B** (contest-allowed family); only the GGUF precision
changes. Vong-1 is pred-upload (accuracy only, Time irrelevant) → use the best quant freely.

## Plan (GPU, one session)

Rent ≥40GB (A6000/A40) so Q8_0 fits. Download + run the full 463, k=1, reasoning_max_tokens
2048, safety ON, constrained-repair ON (the shipped config), for:
- **Q8_0** (~28GB) — near-lossless upper bound: how much accuracy is the quant actually
  costing on the real test?
- **Q6_K** (~22GB) — the VRAM/speed sweet spot that also fits a 24GB judge GPU.

Compare each pred to the Q4 88.55 baseline (`gemma26_safety_probe.csv`) and to the 91.79
frontier reference. Ship the winner for the Vong-1 team-nick upload; pick the Vong-2 Docker
quant by the accuracy-vs-VRAM/Time trade.

## Honesty caveats
- The −4pp is a **math-proxy** number; leaderboard transfer *magnitude* is unproven
  (proxies give direction, not magnitude). Q8≈Q4 on the real 463 would mean the quant loss
  does not transfer → stop and keep Q4.
- Q8 26B (~28GB) does NOT fit a 24GB judge GPU; if the BTC GPU is 24GB the Vong-2 Docker
  must use Q6_K/Q5_K_M, even if Q8 wins Vong-1. Keep the two decisions separate.

## Results
(to be filled after the GPU run)
