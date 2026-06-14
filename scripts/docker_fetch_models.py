"""Download the Gemma main GGUF (and, when requested, the MTP draft GGUF) into a
target directory during a Docker/Kaniko build.

Kaniko does not support BuildKit `--mount=type=secret` or heredoc `RUN` blocks
reliably (see docs/runpod-operations.md "Kaniko Build Lessons"), so the
Kaniko Dockerfiles call this checked-in script instead of an inline heredoc.

The gated main model is authenticated via the ``HF_TOKEN`` / ``HUGGING_FACE_HUB_TOKEN``
environment variable, which ``huggingface_hub`` reads automatically. The token is
NEVER written into the image: it stays in the build process environment only.

Usage (env-driven, matching the Dockerfile ARG names):

    MAIN_REPO=... MAIN_FILE=... python scripts/docker_fetch_models.py
    # plus DRAFT_REPO/DRAFT_FILE and --with-draft to also fetch the MTP draft
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import hf_hub_download


def _token() -> str | None:
    return (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or None
    )


def _fetch(repo_id: str, candidates: tuple[str, ...], target_dir: Path, flat_name: str) -> Path:
    """Download the first reachable candidate filename and normalise it to ``flat_name``."""
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename=candidate,
                local_dir=target_dir,
                token=_token(),
            )
        except Exception as error:  # noqa: BLE001 - report the last failure if all candidates miss
            last_error = error
            continue
        flat = target_dir / flat_name
        if not flat.exists():
            Path(downloaded).replace(flat)
        if flat.stat().st_size <= 0:
            raise SystemExit(f"downloaded file is empty: {flat}")
        return flat
    raise SystemExit(f"could not download {flat_name} from {repo_id}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", default="/models")
    parser.add_argument("--with-draft", action="store_true", help="also fetch the MTP draft GGUF")
    args = parser.parse_args()

    target_dir = Path(args.target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    main_repo = os.environ["MAIN_REPO"]
    main_file = os.environ["MAIN_FILE"]
    main_path = _fetch(main_repo, (main_file,), target_dir, main_file)
    print(f"main={main_path} ({main_path.stat().st_size} bytes)")

    if args.with_draft:
        draft_repo = os.environ["DRAFT_REPO"]
        draft_file = os.environ["DRAFT_FILE"]
        # The MTP draft GGUF is published either at the repo root or under MTP/.
        draft_path = _fetch(
            draft_repo,
            (draft_file, f"MTP/{draft_file}"),
            target_dir,
            draft_file,
        )
        print(f"draft={draft_path} ({draft_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
