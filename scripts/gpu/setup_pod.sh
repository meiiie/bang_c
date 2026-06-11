#!/usr/bin/env bash
# One-shot pod setup for the per-bucket measurement battery.
#
# Windows -> pod hygiene (notes/lessons.md): write file -> scp -> tr -d '\r' -> bash.
# Expected layout: repo synced to /workspace/neko-core (no secrets/outputs/models).
#
# Community pods often have pre-AVX512 CPUs: prebuilt llama-cpp wheels SIGILL with
# EMPTY logs (exit 132). We therefore SOURCE-BUILD llama-cpp-python with CUDA.
# Budget ~40 min for the build (lesson from GPU session 2).
set -euo pipefail
cd /workspace/neko-core

python -m pip install --upgrade pip
python -m pip install requests "huggingface-hub>=0.32,<1" gdown pyarrow
CMAKE_ARGS="-DGGML_CUDA=on" FORCE_CMAKE=1 \
  python -m pip install "llama-cpp-python>=0.3.9,<0.4" --no-binary llama-cpp-python -v

# Volume paths first, symlinks second — and never pre-create the symlink target
# (a real /models dir on the small container disk killed a 14GB extraction once).
mkdir -p /workspace/models /workspace/devsets /workspace/out /workspace/data-rag
[ -e /models ] || ln -sfn /workspace/models /models

python - <<'PY'
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id="google/gemma-4-26B-A4B-it-qat-q4_0-gguf",
    filename="gemma-4-26B_q4_0-it.gguf",
    local_dir="/workspace/models",
)
PY
test -s /workspace/models/gemma-4-26B_q4_0-it.gguf

# Sanity: the harness itself must be green before any measurement.
python -m unittest discover -s tests
PYTHONPATH=src python -m hackaithon_c.run --policy

# Battery inputs: labeled dev sets + the RAG corpus.
# Prefer the locally-built, locally-validated devsets (scp'd before this script);
# rebuild on the pod only when they are absent.
if [ ! -s /workspace/devsets/quant.json ]; then
  python scripts/gpu/make_devsets.py --out /workspace/devsets
fi
python scripts/build_rag_corpus.py \
  --out /workspace/data-rag/legal_corpus.jsonl \
  --cache /workspace/data-rag/corpus.parquet
echo "POD SETUP DONE"
