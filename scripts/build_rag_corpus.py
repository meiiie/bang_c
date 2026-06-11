"""Build the offline JSONL retrieval corpus for the targeted legal/admin RAG mode.

DEV-SIDE ONLY (needs network + pyarrow): the contest runtime never downloads anything —
it loads the JSONL this script produces via `rag_corpus_path`.

Source: YuITC/Vietnamese-Legal-Documents corpus.parquet (MIT, 119,007 Vietnamese legal
documents, columns {cid, text}). Fallback if it vanishes (HF datasets do disappear —
see notes/lessons.md): th1nhng0/vietnamese-legal-documents (CC-BY 4.0, raw HTML from
vbpl.vn — needs HTML stripping, not implemented here on purpose; this script fails
loudly so the operator can decide).

Chunking: Vietnamese statutes are organized in "Điều N." (Article N) units — the
natural retrieval granularity. Split on article boundaries, pack tiny articles
together, and hard-wrap oversized ones on paragraph breaks. Diacritics are preserved
end to end (meaning-bearing; see notes/lessons.md 2026-06-10).

Usage (from the repo root):
    .venv/Scripts/python scripts/build_rag_corpus.py [--out data/rag/legal_corpus.jsonl]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

CORPUS_URL = (
    "https://huggingface.co/datasets/YuITC/Vietnamese-Legal-Documents/"
    "resolve/main/corpus.parquet"
)
ARTICLE_BOUNDARY = re.compile(r"\n(?=Điều\s+\d+\s*[.:])")
MIN_CHUNK_CHARS = 120
MAX_CHUNK_CHARS = 1500


def chunk_document(text: str) -> list[str]:
    """Split one legal document into retrieval chunks on article boundaries."""
    chunks: list[str] = []
    pending = ""
    for part in ARTICLE_BOUNDARY.split(text):
        part = part.strip()
        if not part:
            continue
        if len(pending) + len(part) + 1 <= MIN_CHUNK_CHARS:
            pending = f"{pending}\n{part}".strip()
            continue
        if pending:
            part = f"{pending}\n{part}"
            pending = ""
        while len(part) > MAX_CHUNK_CHARS:
            split_at = part.rfind("\n", MIN_CHUNK_CHARS, MAX_CHUNK_CHARS)
            if split_at == -1:
                split_at = MAX_CHUNK_CHARS
            chunks.append(part[:split_at].strip())
            part = part[split_at:].strip()
        if len(part) >= MIN_CHUNK_CHARS:
            chunks.append(part)
        else:
            pending = part
    if pending and len(pending) >= MIN_CHUNK_CHARS:
        chunks.append(pending)
    return chunks


def document_title(text: str) -> str:
    """First non-empty line, capped — legal documents open with their own title."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:160]
    return ""


def download(url: str, destination: Path, *, attempts: int = 5) -> None:
    """Resumable download: stream to a .tmp file, resume with HTTP Range on broken
    connections, rename only when complete (a partial file is never mistaken for a
    finished one)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        print(f"reuse cached {destination} ({destination.stat().st_size / 1e6:.0f} MB)")
        return
    partial = destination.with_suffix(destination.suffix + ".tmp")
    print(f"downloading {url}")
    for attempt in range(1, attempts + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with requests.get(url, stream=True, timeout=120, headers=headers) as response:
                if offset and response.status_code != 206:
                    offset = 0  # server ignored Range; restart from scratch
                response.raise_for_status()
                mode = "ab" if offset else "wb"
                with partial.open(mode) as handle:
                    for block in response.iter_content(chunk_size=1 << 20):
                        handle.write(block)
            partial.rename(destination)
            print(f"saved {destination} ({destination.stat().st_size / 1e6:.0f} MB)")
            return
        except requests.RequestException as error:
            print(f"attempt {attempt}/{attempts} failed: {error}")
            if attempt == attempts:
                raise
    raise requests.RequestException("download retries exhausted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/rag/legal_corpus.jsonl")
    parser.add_argument("--cache", default="data/rag/corpus.parquet")
    parser.add_argument(
        "--max-docs", type=int, default=0, help="0 = all documents (debug aid)"
    )
    args = parser.parse_args()

    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("pyarrow is required: .venv/Scripts/python -m pip install pyarrow")
        return 1

    cache = Path(args.cache)
    try:
        download(CORPUS_URL, cache)
    except requests.RequestException as error:
        print(f"FAILED to download YuITC corpus: {error}")
        print(
            "Fallback source (manual): th1nhng0/vietnamese-legal-documents "
            "(CC-BY, raw HTML — needs cleaning before use)."
        )
        return 1

    table = pq.read_table(cache, columns=["cid", "text"])
    cids = table.column("cid").to_pylist()
    texts = table.column("text").to_pylist()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    documents = 0
    chunks = 0
    # Write to .tmp and rename: an interrupted build must never leave a truncated
    # JSONL that the runtime then re-parses-and-fails on every RAG-routed question.
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        for cid, text in zip(cids, texts):
            if args.max_docs and documents >= args.max_docs:
                break
            if not text or len(text.strip()) < MIN_CHUNK_CHARS:
                continue
            documents += 1
            title = document_title(text)
            for index, chunk in enumerate(chunk_document(text)):
                handle.write(
                    json.dumps(
                        {"id": f"{cid}-{index}", "title": title, "text": chunk},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                chunks += 1
    tmp_path.replace(out_path)
    print(f"wrote {chunks} chunks from {documents} documents to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
