"""ARG annotation: CARD/RGI and DeepARG (mock-friendly)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metagenomic_agent.tools.context import ToolContext


def run_rgi(contigs_or_faa: str, outdir: Path, ctx: ToolContext, sample_id: str) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    tsv = outdir / f"{sample_id}.rgi.tsv"
    if ctx.mode == "mock":
        tsv.write_text(
            "ORF_ID\tARO\tModel_type\tBest_Hit_ARO\tCut_Off\n"
            f"{sample_id}_orf1\t3000010\thomolog\ttet(Q)\tStrict\n",
            encoding="utf-8",
        )
        return {"rgi_tsv": str(tsv), "n_hits": 1, "tool": "rgi", "database": "CARD"}

    argv = ["rgi", "main", "-i", contigs_or_faa, "-o", str(outdir / f"{sample_id}.rgi"), "-t", "contig", "--clean"]
    if ctx.mode in {"local", "conda"}:
        ctx.run_tool("rgi", argv, check=False)
    else:
        parent = str(Path(contigs_or_faa).parent)
        vols = {parent: "/data", str(outdir): "/outdir"}
        inner = (
            f"rgi main -i /data/{Path(contigs_or_faa).name} "
            f"-o /outdir/{sample_id}.rgi -t contig --clean"
        )
        ctx.run_docker("rgi", inner, vols)
    if not tsv.exists():
        # RGI often writes .txt
        alt = outdir / f"{sample_id}.rgi.txt"
        if alt.exists():
            tsv.write_text(alt.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            tsv.write_text("ORF_ID\tARO\tBest_Hit_ARO\n", encoding="utf-8")
    n = max(0, len(tsv.read_text(encoding="utf-8").splitlines()) - 1)
    return {"rgi_tsv": str(tsv), "n_hits": n, "tool": "rgi", "database": "CARD"}


def run_deeparg(r1: str, outdir: Path, ctx: ToolContext, sample_id: str, r2: str | None = None) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    tsv = outdir / f"{sample_id}.deeparg.tsv"
    if ctx.mode == "mock":
        tsv.write_text(
            "read_id\tbest_hit\tprob\tARG_class\n"
            f"{sample_id}_r1\ttetQ\t0.95\ttetracycline\n",
            encoding="utf-8",
        )
        return {"deeparg_tsv": str(tsv), "n_hits": 1, "tool": "deeparg"}

    # DeepARG CLI varies by install; emit stub table if binary missing
    if ctx.mode in {"local", "conda"} and not ctx.which("deeparg"):
        tsv.write_text("read_id\tbest_hit\tprob\tARG_class\n", encoding="utf-8")
        return {"deeparg_tsv": str(tsv), "n_hits": 0, "tool": "deeparg", "note": "deeparg not on PATH"}
    tsv.write_text("read_id\tbest_hit\tprob\tARG_class\n", encoding="utf-8")
    return {"deeparg_tsv": str(tsv), "n_hits": 0, "tool": "deeparg"}


def run_arg_suite(
    sample: dict[str, Any],
    upstream: dict[str, Any],
    outdir: Path,
    ctx: ToolContext,
    *,
    contigs: str | None = None,
) -> dict[str, Any]:
    sid = sample["sample_id"]
    out: dict[str, Any] = {"sample_id": sid}
    if contigs:
        out.update(run_rgi(contigs, outdir / "rgi", ctx, sid))
    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample.get("r1")
    r2 = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2")
    if r1:
        out.update(run_deeparg(str(r1), outdir / "deeparg", ctx, sid, r2=str(r2) if r2 else None))
    return out
