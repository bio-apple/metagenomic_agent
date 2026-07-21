"""Strict Pydantic schemas for common metagenomic tools — validate before execution.

Agents emit structured params (dict/YAML); never free-form shell. Schemas reject
illegal paths, threads, and memory before sandbox invocation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def _path_ok(v: str, *, allow_placeholder: bool = True) -> str:
    s = (v or "").strip()
    if not s:
        raise ValueError("path must be non-empty")
    if allow_placeholder and (s.startswith("<") or s.startswith("results/")):
        return s
    # Reject obvious shell injection characters in paths
    for bad in (";", "|", "`", "$(", "&&", "||", "\n"):
        if bad in s:
            raise ValueError(f"illegal characters in path: {bad!r}")
    return s


class BaseToolParams(BaseModel):
    """Shared resource limits for all tools."""

    threads: int = Field(default=8, ge=1, le=256, description="CPU threads (-t)")
    memory_gb: int = Field(default=16, ge=1, le=1024, description="Memory limit GB (-m)")
    outdir: str = Field(default="results", description="Output directory")

    @field_validator("outdir")
    @classmethod
    def _v_outdir(cls, v: str) -> str:
        return _path_ok(v)


class FastpParams(BaseToolParams):
    tool: Literal["fastp"] = "fastp"
    r1: str
    r2: str | None = None
    qualified_quality_phred: int = Field(default=20, ge=5, le=40)
    length_required: int = Field(default=36, ge=15, le=500)

    @field_validator("r1", "r2")
    @classmethod
    def _v_reads(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)


class FastQCParams(BaseToolParams):
    tool: Literal["fastqc"] = "fastqc"
    inputs: list[str] = Field(..., min_length=1)

    @field_validator("inputs")
    @classmethod
    def _v_inputs(cls, v: list[str]) -> list[str]:
        return [_path_ok(x) for x in v]


class TrimmomaticParams(BaseToolParams):
    tool: Literal["trimmomatic"] = "trimmomatic"
    r1: str
    r2: str | None = None
    adapters: str | None = None
    leading: int = Field(default=3, ge=0, le=40)
    trailing: int = Field(default=3, ge=0, le=40)
    minlen: int = Field(default=36, ge=15, le=500)

    @field_validator("r1", "r2", "adapters")
    @classmethod
    def _v_paths(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)


class Kraken2Params(BaseToolParams):
    tool: Literal["kraken2"] = "kraken2"
    r1: str
    r2: str | None = None
    db: str
    confidence: float = Field(default=0.05, ge=0.0, le=1.0)
    memory_mapping: bool = True

    @field_validator("r1", "r2", "db")
    @classmethod
    def _v_paths(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)

    @model_validator(mode="after")
    def _db_not_empty(self) -> Kraken2Params:
        if not self.db or self.db == "<db>":
            # allow placeholder at plan time; execution layer may still fail closed
            pass
        return self


class MegahitParams(BaseToolParams):
    tool: Literal["megahit"] = "megahit"
    r1: str
    r2: str | None = None
    min_contig_len: int = Field(default=200, ge=100, le=10000)
    memory_gb: int = Field(default=32, ge=4, le=1024)

    @field_validator("r1", "r2")
    @classmethod
    def _v_reads(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)


class MetaBAT2Params(BaseToolParams):
    tool: Literal["metabat2"] = "metabat2"
    contigs: str
    bam: str | None = None
    min_contig: int = Field(default=1500, ge=500, le=100000)

    @field_validator("contigs", "bam")
    @classmethod
    def _v_paths(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)


class HUMAnN3Params(BaseToolParams):
    tool: Literal["humann3"] = "humann3"
    input: str
    nucleotide_db: str | None = None
    protein_db: str | None = None
    threads: int = Field(default=8, ge=1, le=128)

    @field_validator("input", "nucleotide_db", "protein_db")
    @classmethod
    def _v_paths(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)


class CheckM2Params(BaseToolParams):
    tool: Literal["checkm2"] = "checkm2"
    bins_dir: str
    extension: str = Field(default="fa", pattern=r"^[A-Za-z0-9_.-]{1,16}$")

    @field_validator("bins_dir")
    @classmethod
    def _v_bins(cls, v: str) -> str:
        return _path_ok(v)


class GTDBTkParams(BaseToolParams):
    tool: Literal["gtdbtk"] = "gtdbtk"
    bins_dir: str
    extension: str = Field(default="fa", pattern=r"^[A-Za-z0-9_.-]{1,16}$")
    threads: int = Field(default=16, ge=1, le=256)

    @field_validator("bins_dir")
    @classmethod
    def _v_bins(cls, v: str) -> str:
        return _path_ok(v)


class BaktaParams(BaseToolParams):
    tool: Literal["bakta"] = "bakta"
    input: str
    db: str
    prefix: str = Field(default="bakta", pattern=r"^[A-Za-z0-9_.-]{1,64}$")

    @field_validator("input", "db")
    @classmethod
    def _v_paths(cls, v: str) -> str:
        return _path_ok(v)


class MetaPhlAnParams(BaseToolParams):
    tool: Literal["metaphlan"] = "metaphlan"
    r1: str
    r2: str | None = None
    db: str | None = None

    @field_validator("r1", "r2", "db")
    @classmethod
    def _v_paths(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)


class ConcoctParams(BaseToolParams):
    tool: Literal["concoct"] = "concoct"
    composition_file: str
    coverage_file: str | None = None

    @field_validator("composition_file", "coverage_file")
    @classmethod
    def _v_paths(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _path_ok(v)


class RGIParams(BaseToolParams):
    tool: Literal["rgi"] = "rgi"
    input: str
    input_type: str = "contig"

    @field_validator("input")
    @classmethod
    def _v_paths(cls, v: str) -> str:
        return _path_ok(v)


class VirSorter2Params(BaseToolParams):
    tool: Literal["virsorter2"] = "virsorter2"
    contigs: str
    min_length: int = Field(default=3000, ge=500)

    @field_validator("contigs")
    @classmethod
    def _v_paths(cls, v: str) -> str:
        return _path_ok(v)


class CheckVParams(BaseToolParams):
    tool: Literal["checkv"] = "checkv"
    viral_fasta: str

    @field_validator("viral_fasta")
    @classmethod
    def _v_paths(cls, v: str) -> str:
        return _path_ok(v)


TOOL_SCHEMA_REGISTRY: dict[str, type[BaseToolParams]] = {
    "fastp": FastpParams,
    "fastqc": FastQCParams,
    "trimmomatic": TrimmomaticParams,
    "kraken2": Kraken2Params,
    "megahit": MegahitParams,
    "metabat2": MetaBAT2Params,
    "concoct": ConcoctParams,
    "humann3": HUMAnN3Params,
    "humann": HUMAnN3Params,
    "checkm2": CheckM2Params,
    "gtdbtk": GTDBTkParams,
    "bakta": BaktaParams,
    "metaphlan": MetaPhlAnParams,
    "metaphlan4": MetaPhlAnParams,
    "rgi": RGIParams,
    "virsorter2": VirSorter2Params,
    "checkv": CheckVParams,
}


class ValidationResult(BaseModel):
    tool: str
    ok: bool
    params: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


def validate_tool_params(tool: str, params: dict[str, Any], *, strict: bool = False) -> ValidationResult:
    """Validate tool parameters against the registered Pydantic schema."""
    name = (tool or "").lower().strip()
    model = TOOL_SCHEMA_REGISTRY.get(name)
    if model is None:
        if strict:
            return ValidationResult(tool=name, ok=False, errors=[f"no schema registered for tool '{name}'"])
        # Soft allow unknown tools with base resource checks
        try:
            base = BaseToolParams.model_validate(
                {k: params[k] for k in ("threads", "memory_gb", "outdir") if k in params}
                or {"threads": params.get("threads", 8), "memory_gb": params.get("memory_gb", 16)}
            )
            return ValidationResult(tool=name, ok=True, params={**params, **base.model_dump()})
        except Exception as exc:  # noqa: BLE001
            return ValidationResult(tool=name, ok=False, errors=[str(exc)])

    try:
        # Map common aliases
        data = dict(params)
        if "memory" in data and "memory_gb" not in data:
            try:
                data["memory_gb"] = int(float(data["memory"]) * 64) if float(data["memory"]) <= 1 else int(data["memory"])
            except (TypeError, ValueError):
                pass
        obj = model.model_validate(data)
        return ValidationResult(tool=name, ok=True, params=obj.model_dump())
    except Exception as exc:  # noqa: BLE001
        errs = []
        # pydantic ValidationError has .errors()
        if hasattr(exc, "errors"):
            try:
                errs = [f"{e.get('loc')}: {e.get('msg')}" for e in exc.errors()]  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                errs = [str(exc)]
        else:
            errs = [str(exc)]
        return ValidationResult(tool=name, ok=False, errors=errs)


def validate_many(tool_param_list: list[dict[str, Any]], *, strict: bool = False) -> list[ValidationResult]:
    out = []
    for item in tool_param_list:
        tool = item.get("tool") or item.get("name") or ""
        params = item.get("params") or item
        out.append(validate_tool_params(str(tool), dict(params), strict=strict))
    return out
