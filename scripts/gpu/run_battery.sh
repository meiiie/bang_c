#!/usr/bin/env bash
# Per-bucket battery: incumbent (self-consistency) vs promotion candidate (router).
#
# Measurement validity (notes/lessons.md): runs the EXACT contest runtime —
# in-process sequential llama-cpp-python — never the faster server path.
# The router arm runs with the RAG corpus configured (that IS the candidate config);
# RAG still only fires on has_legal_admin items, so other buckets are unaffected.
set -euo pipefail
cd /workspace/neko-core

DEVSETS=/workspace/devsets
OUT=/workspace/out

# Candidate config = default + rag_corpus_path (kept out of git; generated here).
python - <<'PY'
import json
from pathlib import Path

config = json.loads(Path("configs/default.json").read_text(encoding="utf-8"))
config["runtime"]["rag_corpus_path"] = "/workspace/data-rag/legal_corpus.jsonl"
Path("/workspace/router-rag-config.json").write_text(
    json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
)
PY

run_arm() {
  local bucket="$1" workflow="$2" config_arg="$3"
  local tag="${bucket}-${workflow}"
  echo "=== ${tag} ==="
  local started=${SECONDS}
  PYTHONUNBUFFERED=1 PYTHONPATH=src \
    python -m hackaithon_c.run \
      --workflow "${workflow}" ${config_arg} \
      --input "${DEVSETS}/${bucket}.json" \
      --output-dir "${OUT}/${tag}" \
      --trace-dir "${OUT}/${tag}/traces" \
      --run-dir "${OUT}/${tag}/run" \
      --auto-resume --checkpoint-every 5 \
      || { echo "ARM FAILED: ${tag}"; exit 1; }
  echo "${tag} wall_seconds=$((SECONDS - started))" | tee -a "${OUT}/timings.txt"
}

# Arms (decided on LOCAL routing analysis, 2026-06-11):
# - quant   : router (shipped behavior; math-syntax cue routes the LaTeX items to TIR).
# - reading : FORCED reading mode — ViMMRC passages are short and marker-less, so the
#             router's long-context gate barely fires on this proxy (2/150); the
#             lever is measured directly, routing was validated on the real 463.
# - civics  : FORCED rag mode — only 13/150 carry >=2 legal markers; forcing measures
#             the retrieval lever on every item.
run_arm "quant" "self-consistency" ""
run_arm "quant" "router" "--config /workspace/router-rag-config.json"
run_arm "reading" "self-consistency" ""
run_arm "reading" "reading" ""
run_arm "civics" "self-consistency" ""
run_arm "civics" "rag" "--config /workspace/router-rag-config.json"

python scripts/gpu/score_battery.py --devsets "${DEVSETS}" --out "${OUT}" \
  | tee "${OUT}/battery-report.txt"
echo "BATTERY DONE"
