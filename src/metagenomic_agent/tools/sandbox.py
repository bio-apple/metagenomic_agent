"""MCP-style sandboxed tool interface — typed inputs, container-isolated execution.

Agents call tools through this layer instead of raw host shell commands.
Backends: mock | local | conda | docker | apptainer (Singularity).
"""

from __future__ import annotations

import platform
import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from metagenomic_agent.tools.docker_runner import RunResult, apptainer_run, docker_run, run_command
from metagenomic_agent.tools.linux_runner import CommandResult, LinuxBioToolRunner, classify_error


class SandboxBackend(str, Enum):
    MOCK = "mock"
    LOCAL = "local"
    CONDA = "conda"
    DOCKER = "docker"
    APPTAINER = "apptainer"


class ToolCallRequest(BaseModel):
    """Strongly typed tool invocation (MCP-like tool call)."""

    tool: str = Field(..., description="Logical tool name, e.g. kraken2")
    argv: list[str] = Field(default_factory=list, description="Command argv inside the sandbox")
    workdir: str | None = None
    volumes: dict[str, str] = Field(default_factory=dict, description="host_path -> container_path")
    env: dict[str, str] = Field(default_factory=dict)
    threads: int = Field(default=8, ge=1, le=256)
    memory_gb: int = Field(default=16, ge=1, le=1024)
    timeout_s: int = Field(default=3600, ge=30)
    platform: Literal["auto", "linux/amd64", "linux/arm64"] = "auto"
    image: str | None = None
    conda_env: str | None = None
    check: bool = False


class ToolCallResponse(BaseModel):
    ok: bool
    tool: str
    backend: str
    command: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    classified: str | None = None
    user_message: str = ""
    recovery_hints: list[str] = Field(default_factory=list)
    image: str | None = None


def detect_host_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "linux/arm64"
    return "linux/amd64"


def friendly_error_message(classified: str | None, stderr: str, tool: str) -> tuple[str, list[str]]:
    """Translate stderr into user-facing guidance (do not dump raw logs by default)."""
    text = (stderr or "").lower()
    hints: list[str] = []
    if classified == "oom":
        msg = f"工具 `{tool}` 因内存不足失败（常见于 exit 137）。"
        hints = ["降低 threads/memory_gb", "改用 MEGAHIT 替代 metaSPAdes", "切换 Docker/Apptainer 并限制 --memory"]
    elif classified == "missing_binary":
        msg = f"工具 `{tool}` 可执行文件未找到。"
        hints = ["改用 mode=docker/apptainer + biocontainers 镜像", "或安装对应 conda env"]
    elif classified == "arch_mismatch":
        msg = f"架构不兼容（Apple Silicon / ARM 与 x86 镜像冲突）。"
        hints = ["设置 sandbox.platform=linux/amd64 并通过 Docker 模拟", "或改用原生 arm64 biocontainer"]
    elif classified == "missing_library":
        msg = f"动态库缺失（glibc/libstdc++ 等），宿主机直接运行不安全。"
        hints = ["强制容器隔离（docker/apptainer）", "避免 local 模式跑生信二进制"]
    elif classified == "timeout":
        msg = f"工具 `{tool}` 超时。"
        hints = ["增加 timeout", "降低数据量或 threads"]
    elif classified == "resource":
        msg = f"磁盘或权限等资源错误。"
        hints = ["检查磁盘空间与输出目录写权限"]
    elif "conda" in text and ("not found" in text or "environment" in text):
        msg = f"Conda 环境不可用。"
        hints = ["创建 conda env", "或切换 docker/apptainer"]
        classified = classified or "missing_binary"
    else:
        msg = f"工具 `{tool}` 执行失败（已捕获 stderr，系统将尝试自愈）。"
        hints = ["查看 artifacts.errors 中的 classified 字段", "允许 self-heal 自动降参重试"]
    # Keep only a short, sanitized one-line excerpt (avoid dumping stacks)
    excerpt_lines = [ln.strip() for ln in (stderr or "").strip().splitlines() if ln.strip()]
    if excerpt_lines:
        last = excerpt_lines[-1]
        if len(last) > 120:
            last = last[:117] + "..."
        # Skip useless repeated filler
        if last.lower() not in {"killed", "killed."} and "long stack" not in last.lower():
            msg += f" 摘要: {last}"
        elif last.lower() in {"killed", "killed."}:
            msg += " 摘要: process killed (OOM 嫌疑)"
    return msg, hints


@dataclass
class SandboxExecutor:
    """Execute ToolCallRequest on an isolated backend."""

    backend: SandboxBackend
    images: dict[str, str] = field(default_factory=dict)
    conda_envs: dict[str, str] = field(default_factory=dict)
    default_platform: str = "auto"
    prefer_container: bool = True

    def resolve_backend(self, req: ToolCallRequest) -> SandboxBackend:
        if self.backend == SandboxBackend.MOCK:
            return SandboxBackend.MOCK
        # Prefer containers when configured — avoid fragile host execution
        if self.prefer_container and self.backend in {SandboxBackend.DOCKER, SandboxBackend.APPTAINER}:
            return self.backend
        if self.backend == SandboxBackend.LOCAL and self.prefer_container and self.images.get(req.tool):
            return SandboxBackend.DOCKER
        return self.backend

    def execute(self, req: ToolCallRequest, *, schema_params: dict[str, Any] | None = None) -> ToolCallResponse:
        # Optional Pydantic schema gate before any sandbox/backend launch
        if schema_params is not None or req.tool in {
            "fastp",
            "fastqc",
            "trimmomatic",
            "kraken2",
            "megahit",
            "metabat2",
            "humann3",
            "humann",
            "checkm2",
            "gtdbtk",
            "bakta",
            "metaphlan",
        }:
            from metagenomic_agent.tools.schemas import validate_tool_params

            payload = dict(schema_params or {})
            payload.setdefault("threads", req.threads)
            payload.setdefault("memory_gb", req.memory_gb)
            if req.workdir:
                payload.setdefault("outdir", req.workdir)
            vr = validate_tool_params(req.tool, payload, strict=False)
            if not vr.ok and schema_params is not None:
                return ToolCallResponse(
                    ok=False,
                    tool=req.tool,
                    backend=self.backend.value,
                    command=" ".join(req.argv),
                    classified="logic",
                    user_message=f"参数 Schema 校验失败: {'; '.join(vr.errors)}",
                    recovery_hints=["修正 YAML/JSON 参数后重试", "检查路径 / threads / memory_gb"],
                    stderr="; ".join(vr.errors),
                )
            if vr.ok:
                req.threads = int(vr.params.get("threads", req.threads))
                req.memory_gb = int(vr.params.get("memory_gb", req.memory_gb))

        backend = self.resolve_backend(req)
        if backend == SandboxBackend.MOCK:
            return ToolCallResponse(
                ok=True,
                tool=req.tool,
                backend="mock",
                command=" ".join(req.argv) or f"mock:{req.tool}",
                returncode=0,
                stdout="mock ok",
                user_message=f"mock 执行 `{req.tool}` 成功",
            )

        plat = req.platform if req.platform != "auto" else (
            self.default_platform if self.default_platform != "auto" else detect_host_arch()
        )
        # On Apple Silicon, default docker bio images are often amd64
        if plat == "linux/arm64" and backend == SandboxBackend.DOCKER:
            # biocontainers are typically amd64 — request emulation unless user overrides
            plat = "linux/amd64"

        image = req.image or self.images.get(req.tool)
        display_cmd = " ".join(shlex.quote(a) for a in req.argv)

        try:
            if backend == SandboxBackend.DOCKER:
                if not image:
                    raise RuntimeError(f"No container image for tool '{req.tool}'")
                result = docker_run(
                    image,
                    display_cmd if not req.argv else " ".join(shlex.quote(a) for a in req.argv),
                    req.volumes,
                    check=False,
                    platform=plat,
                    memory_gb=req.memory_gb,
                    cpus=req.threads,
                    workdir=req.workdir,
                    env=req.env,
                )
                return self._to_response(req, "docker", result, image)
            if backend == SandboxBackend.APPTAINER:
                if not image:
                    raise RuntimeError(f"No container image/SIF for tool '{req.tool}'")
                result = apptainer_run(
                    image,
                    " ".join(shlex.quote(a) for a in req.argv),
                    req.volumes,
                    check=False,
                    env=req.env,
                )
                return self._to_response(req, "apptainer", result, image)
            if backend == SandboxBackend.CONDA:
                runner = LinuxBioToolRunner(
                    conda_env=req.conda_env or self.conda_envs.get(req.tool, "metagenomics"),
                    use_conda=True,
                    default_timeout=req.timeout_s,
                )
                cr = runner.run_command(req.argv, timeout=req.timeout_s, check=False)
                return self._from_command_result(req, "conda", cr, image)
            # local — discouraged
            result = run_command(req.argv, check=False)
            return self._to_response(req, "local", result, None)
        except Exception as exc:  # noqa: BLE001
            classified = classify_error(None, str(exc))
            msg, hints = friendly_error_message(classified, str(exc), req.tool)
            return ToolCallResponse(
                ok=False,
                tool=req.tool,
                backend=backend.value,
                command=display_cmd,
                stderr=str(exc),
                classified=classified,
                user_message=msg,
                recovery_hints=hints,
                image=image,
            )

    def _to_response(self, req: ToolCallRequest, backend: str, result: RunResult, image: str | None) -> ToolCallResponse:
        classified = None if result.ok else classify_error(result.returncode, result.stderr)
        msg, hints = ("ok", []) if result.ok else friendly_error_message(classified, result.stderr, req.tool)
        return ToolCallResponse(
            ok=result.ok,
            tool=req.tool,
            backend=backend,
            command=result.command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr if not result.ok else "",
            classified=classified,
            user_message=msg if result.ok else msg,
            recovery_hints=hints,
            image=image,
        )

    def _from_command_result(
        self, req: ToolCallRequest, backend: str, cr: CommandResult, image: str | None
    ) -> ToolCallResponse:
        ok = cr.status == "success"
        classified = cr.classified
        msg, hints = ("ok", []) if ok else friendly_error_message(classified, cr.stderr or cr.error or "", req.tool)
        return ToolCallResponse(
            ok=ok,
            tool=req.tool,
            backend=backend,
            command=cr.command,
            returncode=cr.returncode,
            stdout=cr.stdout,
            stderr=cr.stderr if not ok else "",
            classified=classified,
            user_message=msg,
            recovery_hints=hints,
            image=image,
        )


def sandbox_from_config(config: dict[str, Any]) -> SandboxExecutor:
    from metagenomic_agent.tools.context import DEFAULT_CONDA_ENVS, DEFAULT_IMAGES

    mode = (config.get("mode") or "mock").lower()
    if mode == "singularity":
        mode = "apptainer"
    sandbox_cfg = config.get("sandbox") or {}
    docker_cfg = config.get("docker") or {}
    linux_cfg = config.get("linux") or {}

    backend_map = {
        "mock": SandboxBackend.MOCK,
        "local": SandboxBackend.LOCAL,
        "conda": SandboxBackend.CONDA,
        "docker": SandboxBackend.DOCKER,
        "apptainer": SandboxBackend.APPTAINER,
        "singularity": SandboxBackend.APPTAINER,
    }
    backend_key = str(sandbox_cfg.get("backend") or mode).lower() or mode
    if not backend_key:
        backend_key = mode
    backend = backend_map.get(backend_key, SandboxBackend.MOCK)
    images = dict(DEFAULT_IMAGES)
    images.update(docker_cfg.get("images") or {})
    conda_envs = dict(DEFAULT_CONDA_ENVS)
    conda_envs.update(linux_cfg.get("conda_envs") or {})
    return SandboxExecutor(
        backend=backend,
        images=images,
        conda_envs=conda_envs,
        default_platform=str(sandbox_cfg.get("platform") or docker_cfg.get("platform") or "auto"),
        prefer_container=bool(sandbox_cfg.get("prefer_container", True)),
    )
