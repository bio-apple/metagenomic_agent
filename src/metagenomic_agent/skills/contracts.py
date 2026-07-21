"""Skill & Contract framework — deterministic pre/post conditions for tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class Severity(str, Enum):
    ERROR = "error"      # block execution / HITL required
    WARNING = "warning"  # continue but flag
    INFO = "info"


@dataclass
class ContractViolation:
    skill: str
    check: str  # pre | post
    message: str
    severity: Severity = Severity.ERROR
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class InputContract:
    """What a skill requires before running."""

    required_artifacts: list[str] = field(default_factory=list)  # keys in sample/upstream
    min_read_length: int | None = None
    max_read_length: int | None = None
    require_paired: bool | None = None
    min_reads: int | None = None
    allowed_platforms: list[str] = field(default_factory=list)
    custom: Callable[[dict[str, Any], dict[str, Any]], list[ContractViolation]] | None = None


@dataclass
class OutputContract:
    """What a skill must produce after running."""

    required_outputs: list[str] = field(default_factory=list)
    min_classification_rate: float | None = None
    min_completeness: float | None = None
    max_contamination: float | None = None
    min_read_retention: float | None = None
    custom: Callable[[dict[str, Any]], list[ContractViolation]] | None = None


@dataclass
class Skill:
    name: str
    description: str
    input_contract: InputContract
    output_contract: OutputContract
    tags: list[str] = field(default_factory=list)


def _has_path(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value:
        return Path(value).exists() if "/" in value or value.endswith((".tsv", ".fastq", ".fa", ".fasta", ".json", ".txt", ".html")) else True
    return bool(value)


def check_preconditions(skill: Skill, sample: dict[str, Any], upstream: dict[str, Any]) -> list[ContractViolation]:
    violations: list[ContractViolation] = []
    ctx = {**sample, **upstream}
    for key in skill.input_contract.required_artifacts:
        if not _has_path(ctx.get(key)) and key not in ctx:
            # allow r1 from sample
            if key == "r1" and sample.get("r1"):
                continue
            if key in sample or key in upstream:
                continue
            violations.append(
                ContractViolation(
                    skill=skill.name,
                    check="pre",
                    message=f"Missing required artifact '{key}' for skill {skill.name}",
                    severity=Severity.ERROR,
                )
            )
    rl = int(sample.get("read_length_est") or 0)
    if skill.input_contract.min_read_length is not None and rl and rl < skill.input_contract.min_read_length:
        violations.append(
            ContractViolation(
                skill=skill.name,
                check="pre",
                message=f"Read length {rl} < min {skill.input_contract.min_read_length} for {skill.name}",
                severity=Severity.ERROR,
                details={"read_length_est": rl},
            )
        )
    if skill.input_contract.max_read_length is not None and rl and rl > skill.input_contract.max_read_length:
        violations.append(
            ContractViolation(
                skill=skill.name,
                check="pre",
                message=f"Read length {rl} > max {skill.input_contract.max_read_length} for {skill.name}",
                severity=Severity.WARNING,
                details={"read_length_est": rl},
            )
        )
    if skill.input_contract.require_paired is True and not sample.get("paired"):
        violations.append(
            ContractViolation(
                skill=skill.name,
                check="pre",
                message=f"Skill {skill.name} requires paired-end reads",
                severity=Severity.WARNING,
            )
        )
    if skill.input_contract.allowed_platforms:
        plat = sample.get("platform") or ""
        if plat and plat not in skill.input_contract.allowed_platforms:
            violations.append(
                ContractViolation(
                    skill=skill.name,
                    check="pre",
                    message=f"Platform '{plat}' not in {skill.input_contract.allowed_platforms}",
                    severity=Severity.WARNING,
                )
            )
    if skill.input_contract.custom:
        violations.extend(skill.input_contract.custom(sample, upstream))
    return violations


def check_postconditions(skill: Skill, outputs: dict[str, Any]) -> list[ContractViolation]:
    violations: list[ContractViolation] = []
    for key in skill.output_contract.required_outputs:
        if not _has_path(outputs.get(key)) and key not in outputs:
            violations.append(
                ContractViolation(
                    skill=skill.name,
                    check="post",
                    message=f"Missing required output '{key}' from skill {skill.name}",
                    severity=Severity.ERROR,
                )
            )
    rate = outputs.get("classification_rate")
    if skill.output_contract.min_classification_rate is not None and rate is not None:
        if float(rate) < skill.output_contract.min_classification_rate:
            violations.append(
                ContractViolation(
                    skill=skill.name,
                    check="post",
                    message=f"Classification rate {rate} < {skill.output_contract.min_classification_rate}",
                    severity=Severity.ERROR,
                    details={"classification_rate": rate},
                )
            )
    if skill.output_contract.min_read_retention is not None and outputs.get("read_retention") is not None:
        if float(outputs["read_retention"]) < skill.output_contract.min_read_retention:
            violations.append(
                ContractViolation(
                    skill=skill.name,
                    check="post",
                    message=f"Read retention {outputs['read_retention']} below contract",
                    severity=Severity.ERROR,
                )
            )
    if skill.output_contract.min_completeness is not None and outputs.get("completeness") is not None:
        if float(outputs["completeness"]) < skill.output_contract.min_completeness:
            violations.append(
                ContractViolation(
                    skill=skill.name,
                    check="post",
                    message=f"MAG completeness {outputs['completeness']} < {skill.output_contract.min_completeness}",
                    severity=Severity.ERROR,
                )
            )
    if skill.output_contract.max_contamination is not None and outputs.get("contamination") is not None:
        if float(outputs["contamination"]) > skill.output_contract.max_contamination:
            violations.append(
                ContractViolation(
                    skill=skill.name,
                    check="post",
                    message=f"MAG contamination {outputs['contamination']} > {skill.output_contract.max_contamination}",
                    severity=Severity.ERROR,
                )
            )
    if skill.output_contract.custom:
        violations.extend(skill.output_contract.custom(outputs))
    return violations
