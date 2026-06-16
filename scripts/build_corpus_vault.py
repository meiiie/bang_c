#!/usr/bin/env python3
"""Compile the markdown current-fact VAULT into the retriever JSONL.

DEV-SIDE ONLY. The source-of-truth is `data/rag/vault/**/*.md` (one atomic fact per file: frontmatter
+ body); this script compiles the ACTIVE facts into the `{id,title,text}` JSONL the BM25+reranker load
(`data/rag/current_vn_2025.jsonl`). The JSONL is a generated artifact — never hand-edit it.

Discipline enforced here (the "no-loạn" guarantees from notes/corpus-vault-harness-design-2026-06-16):
- every chunk MUST carry id + title + source + verified; missing -> rejected (the fact can't ship).
- duplicate `id` -> hard fail (ids must be stable + unique).
- `candidate/` facts (and any `status: candidate`) are EXCLUDED from the ship corpus; pass
  --include-candidates to compile the measurement corpus instead.
- near-duplicate bodies are reported (redundant chunks crowd retrieval — the law-corpus failure mode).

Usage:
  python scripts/build_corpus_vault.py                       # -> data/rag/current_vn_2025.jsonl (active only)
  python scripts/build_corpus_vault.py --include-candidates --out data/rag/candidate_corpus.jsonl
  python scripts/build_corpus_vault.py --check               # compile to a temp + diff vs the live JSONL
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VAULT = REPO / "data" / "rag" / "vault"
DEFAULT_OUT = REPO / "data" / "rag" / "current_vn_2025.jsonl"
REQUIRED = ("id", "title", "source", "verified")


def parse_frontmatter(text: str, path: Path) -> tuple[dict, str]:
    """Minimal frontmatter parser (no yaml dep): a leading '---' fenced block of `key: value` lines,
    then the body. `tags` may be a `[a, b]` list; everything else is a scalar string."""
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing '---' frontmatter block")
    _, fm, body = text.split("---", 2)
    meta: dict = {}
    for line in fm.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}: bad frontmatter line '{line}'")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip().strip('"')
        if key == "tags" and value.startswith("["):
            value = [t.strip() for t in value.strip("[]").split(",") if t.strip()]
        meta[key] = value
    return meta, body.strip()


def load_vault(include_candidates: bool, vault: Path = VAULT) -> list[dict]:
    if not vault.exists():
        raise SystemExit(f"vault not found: {vault} (author facts there first)")
    facts: list[dict] = []
    for md in sorted(vault.rglob("*.md")):
        if md.name.upper() in {"README.MD", "_SCHEMA.MD"}:
            continue
        in_candidate = "candidate" in md.relative_to(vault).parts
        meta, body = parse_frontmatter(md.read_text(encoding="utf-8"), md)
        status = str(meta.get("status", "active")).lower()
        is_candidate = in_candidate or status == "candidate"
        if is_candidate and not include_candidates:
            continue
        missing = [k for k in REQUIRED if not str(meta.get(k, "")).strip()]
        if missing:
            raise SystemExit(f"FAIL {md.relative_to(REPO)}: missing required frontmatter {missing}")
        if not body:
            raise SystemExit(f"FAIL {md.relative_to(REPO)}: empty body (the fact text)")
        if str(meta.get("status", "active")).lower() == "active" \
                and str(meta.get("source_authority", "")).lower() == "secondary":
            print(f"  WARN {md.relative_to(REPO)}: status=active with a SECONDARY source", file=sys.stderr)
        facts.append({"id": str(meta["id"]).strip(), "title": str(meta["title"]).strip(),
                      "text": body, "source": str(meta["source"]).strip(),
                      "verified": str(meta["verified"]).strip(),
                      "_file": str(md.relative_to(REPO)), "_candidate": is_candidate})
    return facts


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile the markdown current-fact vault to retriever JSONL.")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--include-candidates", action="store_true", help="include candidate/ + status:candidate")
    ap.add_argument("--check", action="store_true", help="compile + diff against the existing --out, do not write")
    ap.add_argument("--vault", default=str(VAULT), help="vault dir to compile (default: the current-fact vault)")
    args = ap.parse_args()

    facts = load_vault(args.include_candidates, Path(args.vault).resolve())
    if not facts:
        raise SystemExit("no facts compiled (empty vault?)")

    # duplicate-id hard fail
    seen: dict[str, str] = {}
    for f in facts:
        if f["id"] in seen:
            raise SystemExit(f"FAIL duplicate id '{f['id']}' in {f['_file']} and {seen[f['id']]}")
        seen[f["id"]] = f["_file"]

    # near-duplicate body report (atomic + non-redundant)
    bodies: dict[str, str] = {}
    for f in facts:
        key = f["text"][:60].lower()
        if key in bodies:
            print(f"  NOTE near-dup body: {f['id']} ~ {bodies[key]}", file=sys.stderr)
        bodies[key] = f["id"]

    records = [{"id": f["id"], "title": f["title"], "text": f["text"]} for f in facts]
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)

    by_domain: dict[str, int] = {}
    for f in facts:
        parts = Path(f["_file"]).parts  # data / rag / vault / <domain> / ...
        dom = parts[3] if len(parts) > 4 else "?"
        by_domain[dom] = by_domain.get(dom, 0) + 1
    cand = sum(1 for f in facts if f["_candidate"])
    print(f"compiled {len(records)} facts ({cand} candidate) | by-domain {by_domain}")

    out = Path(args.out)
    if args.check:
        live = out.read_text(encoding="utf-8") if out.exists() else ""
        live_set = {json.dumps(json.loads(l), ensure_ascii=False, sort_keys=True) for l in live.splitlines() if l.strip()}
        new_set = {json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records}
        only_live, only_new = live_set - new_set, new_set - live_set
        if not only_live and not only_new:
            print("CHECK OK: compiled corpus is content-identical to the live JSONL (rag-gated unchanged)")
            return 0
        print(f"CHECK DIFF: only-in-live={len(only_live)} only-in-vault={len(only_new)}")
        for r in list(only_new)[:5]:
            print("  + vault:", r[:90])
        for r in list(only_live)[:5]:
            print("  - live :", r[:90])
        return 1

    out.write_text(payload, encoding="utf-8")
    try:
        shown = out.resolve().relative_to(REPO)
    except ValueError:
        shown = out
    print(f"wrote {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
