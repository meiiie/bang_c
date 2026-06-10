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
neko --input <public_test.csv> --check-submission <pred.csv>
neko --doctor
neko --policy
```

For model or prompt changes, also run a small real-model smoke with
`contest-strict` and inspect the trace.

## Tag

```powershell
git tag v0.4.0
git push origin v0.4.0
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
<dockerhub-user>/neko-core:v0.4.0
<dockerhub-user>/neko-core:latest
```

The tagged GitHub workflow builds the lightweight image. The Gemma local image
is too large for routine GitHub-hosted builds and should be built from a machine
with enough disk/RAM/network:

```powershell
.\scripts\build-gemma-image.ps1 -Image <dockerhub-user>/neko-core:gemma26b-q4
docker push <dockerhub-user>/neko-core:gemma26b-q4
```

Set `HF_TOKEN` outside git only if Hugging Face requires authentication for the
model download. Docker BuildKit passes it as a build secret, not an image env.

Current manually published Gemma image:

```text
hacamy12345/neko-core:gemma26b-q4
hacamy12345/neko-core:gemma26b-q4-20260610
hacamy12345/neko-core@sha256:7034f3a4da3d00bc2de8d7d5ea56422cdeb5e74651a90beba220a962dc0f6760
```

The 2026-06-10 large-image build used `Dockerfile.gemma-local.kaniko` on
RunPod because nested Docker was blocked in the stock pod. If the image is
rebuilt on RunPod, follow `docs/runpod-operations.md` and keep the final
runtime free of API keys.

## Rollback

If a release fails after tag creation:

1. Fix forward on `main`.
2. Tag a new patch version.
3. Do not force-move published tags unless no external artifact has consumed
   the tag yet.
