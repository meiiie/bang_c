param(
    [string] $Image = "neko-core:gemma-local",
    [string] $ModelRepo = "google/gemma-4-26B-A4B-it-qat-q4_0-gguf",
    [string] $ModelFile = "gemma-4-26B_q4_0-it.gguf",
    [string] $LlamaCppExtraIndexUrl = "https://abetlen.github.io/llama-cpp-python/whl/cu124",
    [switch] $CpuOnly
)

$ErrorActionPreference = "Stop"

$extraIndexArg = if ($CpuOnly) { "LLAMA_CPP_EXTRA_INDEX_URL=" } else { "LLAMA_CPP_EXTRA_INDEX_URL=$LlamaCppExtraIndexUrl" }

$args = @(
    "buildx", "build",
    "--file", "Dockerfile.gemma-local",
    "--tag", $Image,
    "--build-arg", "MODEL_REPO=$ModelRepo",
    "--build-arg", "MODEL_FILE=$ModelFile",
    "--build-arg", $extraIndexArg,
    "."
)

if ($env:HF_TOKEN) {
    $args = @(
        "buildx", "build",
        "--secret", "id=HF_TOKEN,env=HF_TOKEN",
        "--file", "Dockerfile.gemma-local",
        "--tag", $Image,
        "--build-arg", "MODEL_REPO=$ModelRepo",
        "--build-arg", "MODEL_FILE=$ModelFile",
        "--build-arg", $extraIndexArg,
        "."
    )
}

docker @args
