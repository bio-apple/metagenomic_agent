"""Lightweight environment and resource probes."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


def probe_environment(docker_image: str = "meta:latest") -> dict[str, Any]:
    info: dict[str, Any] = {
        "docker_available": shutil.which("docker") is not None,
        "docker_image": docker_image,
        "cpus": os.cpu_count() or 1,
        "openai_api_key_set": bool(os.getenv("OPENAI_API_KEY")),
    }
    if info["docker_available"]:
        try:
            subprocess.run(
                ["docker", "image", "inspect", docker_image],
                check=True,
                capture_output=True,
                text=True,
            )
            info["docker_image_present"] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            info["docker_image_present"] = False
    else:
        info["docker_image_present"] = False
    return info
