# HackAIthon 2026 Bang C rules notes - 2026-06-13

Source: `C:\Users\Admin\Downloads\Thể lệ HackAIthon 2026.pdf`, pages 8-9.

## Bang C constraints

- Eligible LLM families:
  - Qwen3.5 Series, models `<= 9B`
  - Gemma-4 Series
- Eligible embedding/rerank families:
  - BGE-m3
  - Qwen-Rerank
- Required output:
  - Docker container on Docker Hub
  - Entrypoint reads `public_test.csv` or `private_test.csv` from `/data`
  - Entrypoint writes `/output/pred.csv`
  - Submission CSV columns: `qid,answer`, where answer is one of `A/B/C/D`
  - GitHub repo must contain code and reproduction instructions for the container
  - Method writeup should explain creativity and effectiveness of the chosen model optimization strategy

## Round 2 scoring surface

- Final tuned Docker due: 2026-06-26.
- Organizer evaluates on private test with 2000 questions from 2026-06-26 to 2026-07-03.
- Criteria named in the PDF:
  - Accuracy
  - Inference time
  - Optimization/creative thinking

The PDF table has a wording inconsistency: the Accuracy row says `80 điểm`, while
the displayed formula multiplies by `70`; the Time and Idea rows are `10` each.
Treat accuracy as the dominant score and speed as the main secondary lever unless
the organizer clarifies otherwise.

## Implications for Neko Core

- Current local-first Gemma-4 26B Q4 direction is rule-compatible.
- Qwen above 9B should not enter the final scoring path.
- Development-only research can use web, subagents, Claude Code, and external
  references, but the final Docker must be offline and reproducible.
- MTP belongs in the Vòng-2 speed story; it should not be mixed with public-test
  answer hacks or hidden state.
