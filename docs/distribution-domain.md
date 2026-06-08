# Distribution Domain

Status: planned

Neko Core does not require a custom domain to satisfy the HackAIthon Bang C
container contract. The domain is a distribution and trust layer for users who
install the CLI outside Docker.

## Recommended Domain Shape

Use a subdomain instead of the root domain:

```text
https://neko.holilihu.online/
https://neko.holilihu.online/install.ps1
https://neko.holilihu.online/install.sh
```

Keep `holilihu.online` available for the broader Holilihu/Wiii ecosystem. The
`neko` subdomain makes the installer memorable without tying the contest image
to web hosting.

## Routing Policy

Prefer immutable release tags for the public install endpoints:

```text
/install.ps1 -> https://raw.githubusercontent.com/meiiie/bang_c/v0.3.1/install.ps1
/install.sh  -> https://raw.githubusercontent.com/meiiie/bang_c/v0.3.1/install.sh
```

Use explicit development endpoints for `main`:

```text
/main/install.ps1 -> https://raw.githubusercontent.com/meiiie/bang_c/main/install.ps1
/main/install.sh  -> https://raw.githubusercontent.com/meiiie/bang_c/main/install.sh
```

This keeps normal users on a tagged release while still allowing fast internal
testing.

## Cloudflare Worker Plan

Deploy `deploy/cloudflare/install-router.js` as a small redirect worker on
`neko.holilihu.online/*`.

Required Cloudflare settings:

- route or custom domain: `neko.holilihu.online/*`
- `NEKO_RELEASE_TAG`: current stable tag, for example `v0.3.1`
- `NEKO_REPO_RAW_BASE`: `https://raw.githubusercontent.com/meiiie/bang_c`
- `NEKO_GITHUB_URL`: `https://github.com/meiiie/bang_c`

The worker should only redirect installer assets and the project home page. It
must not proxy API keys, model calls, contest data, or Docker scoring traffic.

## Why Domain Is Optional

The competition evaluates the Docker container:

```text
/data/public_test.csv or /data/private_test.csv -> /output/pred.csv
```

The install domain improves polish for teammates and reviewers, but it is not
part of the official scoring path. A broken domain must never block the Docker
entrypoint.
