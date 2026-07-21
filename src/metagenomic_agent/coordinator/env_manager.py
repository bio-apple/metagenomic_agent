"""Lightweight environment probes."""

from __future__ import annotations

import os
import shutil
from typing import Any


def probe_environment(docker_image: str | None = None) -> dict[str, Any]:
    return {
        "docker_available": shutil.which("docker") is not None,
        "local_tools": {
            name: bool(shutil.which(name))
            for name in ("fastp", "bowtie2", "kraken2", "bracken", "metaphlan", "megahit", "diamond")
        },
        "cpus": os.cpu_count() or 1,
        "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
    }
