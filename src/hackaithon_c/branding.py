from __future__ import annotations

from .config import HarnessConfig

VERSION = "0.5.0"
DEFAULT_BRAND_NAME = "Neko Core"
DEFAULT_BRAND_SLUG = "neko-core"
DEFAULT_ASCII_LOGO = (
    " _   _      _          ____               ",
    "| \\ | | ___| | _____  / ___|___  _ __ ___ ",
    "|  \\| |/ _ \\ |/ / _ \\| |   / _ \\| '__/ _ \\",
    "| |\\  |  __/   < (_) | |__| (_) | | |  __/",
    "|_| \\_|\\___|_|\\_\\___/ \\____\\___/|_|  \\___|",
)


def brand_name(config: HarnessConfig | None = None) -> str:
    if config is None:
        return DEFAULT_BRAND_NAME
    return config.brand_name


def version_line(config: HarnessConfig | None = None) -> str:
    return f"{brand_name(config)} {VERSION}"


def ascii_logo(config: HarnessConfig | None = None) -> tuple[str, ...]:
    if config is None:
        return DEFAULT_ASCII_LOGO
    return config.ascii_logo or DEFAULT_ASCII_LOGO


def render_banner(config: HarnessConfig | None = None) -> str:
    lines = list(ascii_logo(config))
    lines.append(version_line(config))
    lines.append("HackAIthon 2026 Bang C inference harness")
    return "\n".join(lines)


def render_quickstart(config: HarnessConfig | None = None) -> str:
    return "\n".join(
        (
            render_banner(config),
            "",
            "Quick start:",
            "  neko --doctor",
            "  neko --model-inventory",
            "  neko core --yolo --data-dir /data --output-dir /output",
            "  neko --workflow contest-strict --data-dir /data --output-dir /output",
            "",
            "Local development:",
            "  neko core --yolo --input public_test.json",
            "  neko --workflow contest-strict --input public_test.json --run-dir run-full --auto-resume",
            "  neko --session run-full",
            "",
            "Aliases:",
            "  neko core --doctor",
            "  neko-core --doctor",
        )
    )
