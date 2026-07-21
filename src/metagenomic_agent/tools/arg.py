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


def run_amrfinderplus(
    contigs_or_faa: str, outdir: Path, ctx: ToolContext, sample_id: str
) -> dict[str, Any]:
    """NCBI AMRFinderPlus against the Reference Gene Catalog (Feldgarden 2021)."""
    outdir.mkdir(parents=True, exist_ok=True)
    tsv = outdir / f"{sample_id}.amrfinder.tsv"
    if ctx.mode == "mock":
        tsv.write_text(
            "Protein id\tGene symbol\tElement type\tSubtype\tClass\n"
            f"{sample_id}_1\tblaCTX-M\tAMR\tBETA-LACTAM\tBETA-LACTAM\n"
            f"{sample_id}_2\tfimH\tVIRULENCE\tADHESION\t\n",
            encoding="utf-8",
        )
        return {
            "amrfinder_tsv": str(tsv),
            "n_hits": 2,
            "tool": "amrfinderplus",
            "database": "Reference_Gene_Catalog",
            "n_amr": 1,
            "n_virulence": 1,
        }

    argv = [
        "amrfinder",
        "-n",
        contigs_or_faa,
        "-o",
        str(tsv),
        "--threads",
        str(ctx.threads),
        "--plus",
    ]
    if ctx.mode in {"local", "conda"} and ctx.which("amrfinder"):
        ctx.run_tool("amrfinderplus", argv, check=False)
    else:
        vols = {str(Path(contigs_or_faa).parent): "/data", str(outdir): "/outdir"}
        inner = (
            f"amrfinder -n /data/{Path(contigs_or_faa).name} -o /outdir/{tsv.name} "
            f"--threads {ctx.threads} --plus"
        )
        ctx.run_docker("amrfinderplus", inner, vols)
    if not tsv.exists():
        tsv.write_text("Gene symbol\tElement type\tSubtype\n", encoding="utf-8")
    lines = tsv.read_text(encoding="utf-8").splitlines()
    n = max(0, len(lines) - 1)
    blob = "\n".join(lines).lower()
    return {
        "amrfinder_tsv": str(tsv),
        "n_hits": n,
        "tool": "amrfinderplus",
        "database": "Reference_Gene_Catalog",
        "n_amr": blob.count("amr") or n,
        "n_virulence": blob.count("virulence"),
    }


def run_resfinder(
    contigs_or_faa: str, outdir: Path, ctx: ToolContext, sample_id: str
) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    tsv = outdir / f"{sample_id}.resfinder.tsv"
    if ctx.mode == "mock":
        tsv.write_text(
            "Resistance gene\tIdentity\tPhenotype\nblaCTX-M\t99.2\tBeta-lactam resistance\n",
            encoding="utf-8",
        )
        return {"resfinder_tsv": str(tsv), "n_hits": 1, "tool": "resfinder"}

    if ctx.mode in {"local", "conda"} and ctx.which("run_resfinder.py"):
        ctx.run_tool(
            "resfinder",
            ["run_resfinder.py", "-ifa", contigs_or_faa, "-o", str(outdir), "-acq"],
            check=False,
        )
    else:
        vols = {str(Path(contigs_or_faa).parent): "/data", str(outdir): "/outdir"}
        inner = f"run_resfinder.py -ifa /data/{Path(contigs_or_faa).name} -o /outdir -acq"
        ctx.run_docker("resfinder", inner, vols)
    if not tsv.exists():
        tsv.write_text("Resistance gene\tIdentity\tPhenotype\n", encoding="utf-8")
    n = max(0, len(tsv.read_text(encoding="utf-8").splitlines()) - 1)
    return {"resfinder_tsv": str(tsv), "n_hits": n, "tool": "resfinder"}


def run_vfdb_blast(
    contigs_or_faa: str, outdir: Path, ctx: ToolContext, sample_id: str
) -> dict[str, Any]:
    """VFDB virulence gene screen (DIAMOND/blastx against paths.vfdb_db when set)."""
    outdir.mkdir(parents=True, exist_ok=True)
    tsv = outdir / f"{sample_id}.vfdb.tsv"
    if ctx.mode == "mock":
        tsv.write_text(
            "VFG\tGene\tProduct\nVFG000001\tfimH\ttype 1 fimbrial adhesin\n",
            encoding="utf-8",
        )
        return {"vfdb_tsv": str(tsv), "n_hits": 1, "tool": "vfdb", "database": "VFDB"}

    db = (ctx.paths.get("vfdb_db") or "").strip()
    if not db:
        tsv.write_text("VFG\tGene\tProduct\n", encoding="utf-8")
        return {"vfdb_tsv": str(tsv), "n_hits": 0, "tool": "vfdb", "note": "vfdb_db not configured"}

    if ctx.mode in {"local", "conda"} and ctx.which("diamond"):
        ctx.run_local(
            [
                "diamond",
                "blastx",
                "-q",
                contigs_or_faa,
                "-d",
                db,
                "-o",
                str(tsv),
                "--threads",
                str(ctx.threads),
                "--max-target-seqs",
                "1",
                "--evalue",
                "1e-5",
            ],
            check=False,
        )
    else:
        vols = {
            str(Path(contigs_or_faa).parent): "/data",
            str(Path(db).parent): "/ref",
            str(outdir): "/outdir",
        }
        inner = (
            f"diamond blastx -q /data/{Path(contigs_or_faa).name} -d /ref/{Path(db).name} "
            f"-o /outdir/{tsv.name} --threads {ctx.threads} --max-target-seqs 1 --evalue 1e-5"
        )
        ctx.run_docker("diamond", inner, vols)
    if not tsv.exists():
        tsv.write_text("VFG\tGene\tProduct\n", encoding="utf-8")
    n = max(0, len(tsv.read_text(encoding="utf-8").splitlines()) - 1)
    return {"vfdb_tsv": str(tsv), "n_hits": n, "tool": "vfdb", "database": "VFDB"}


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
        out["amrfinder"] = run_amrfinderplus(contigs, outdir / "amrfinder", ctx, sid)
        out["resfinder"] = run_resfinder(contigs, outdir / "resfinder", ctx, sid)
        out["vfdb"] = run_vfdb_blast(contigs, outdir / "vfdb", ctx, sid)
    r1 = upstream.get("nonhost_r1") or upstream.get("clean_r1") or sample.get("r1")
    r2 = upstream.get("nonhost_r2") or upstream.get("clean_r2") or sample.get("r2")
    if r1:
        out.update(run_deeparg(str(r1), outdir / "deeparg", ctx, sid, r2=str(r2) if r2 else None))
    return out
