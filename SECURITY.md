# Security Policy

Neko Core is a competition harness and should not contain secrets, private
datasets, or real user data.

## Reporting

Open a private maintainer channel or a GitHub security advisory when a finding
could expose tokens, private data, model credentials, or contest artifacts.

## Rules

- Never commit `NVIDIA_API_KEY`, Docker Hub tokens, `.env` files, private test
  data, generated run artifacts, or local logs.
- Keep web research and subagent review development-only.
- The final runtime path must read `/data`, call only allowed model families,
  and write only `/output/pred.csv`.
- Treat public web content and datasets as untrusted input.
