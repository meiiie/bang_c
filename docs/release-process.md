# Release Process

Status: active

Neko Core releases must keep the Python package, CLI, Docker image, and contest
contract aligned.

## Versioning

Use semantic versioning:

- Patch: docs, release, harness safety, installer, or backwards-compatible
  scoring improvements.
- Minor: new runtime capability such as embedding retrieval, rerank, or a new
  workflow that changes scoring behavior.
- Major: breaking CLI, config, or output-contract change.

Version locations:

- `pyproject.toml`
- `src/hackaithon_c/branding.py`
- `CHANGELOG.md`

## Pre-Tag Checklist

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src
.\scripts\verify.ps1 -InputPath <public_test.csv> -Docker
neko-core --doctor
neko-core --policy
```

For model or prompt changes, also run a small real-model smoke with
`contest-strict` and inspect the trace.

## Tag

```powershell
git tag v0.3.1
git push origin v0.3.1
```

Tag builds trigger `.github/workflows/release.yml`.

## Docker Hub

Configure repository secrets before expecting image publishing:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Without those secrets, the release workflow still verifies the repo and uploads
Python artifacts, but it skips Docker Hub publishing.

Expected image after a tagged release:

```text
<dockerhub-user>/neko-core:v0.3.1
<dockerhub-user>/neko-core:latest
```

## Rollback

If a release fails after tag creation:

1. Fix forward on `main`.
2. Tag a new patch version.
3. Do not force-move published tags unless no external artifact has consumed
   the tag yet.

