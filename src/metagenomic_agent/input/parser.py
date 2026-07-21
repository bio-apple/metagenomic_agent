"""FASTQ input parser and validator."""

from __future__ import annotations

import gzip
import re
from pathlib import Path

from metagenomic_agent.state import AgentState, SampleMeta

FASTQ_EXTS = (".fastq", ".fq", ".fastq.gz", ".fq.gz")
R1_RE = re.compile(r"(_R1|_1)(?=(_|\.|$))", re.I)
R2_RE = re.compile(r"(_R2|_2)(?=(_|\.|$))", re.I)


def _is_fastq(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(ext) for ext in FASTQ_EXTS)


def _gzip_ok(path: Path) -> bool:
    if not str(path).endswith(".gz"):
        return True
    with path.open("rb") as f:
        return f.read(2) == b"\x1f\x8b"


def _estimate_read_length(path: Path, max_reads: int = 50) -> int:
    opener = gzip.open if str(path).endswith(".gz") else open
    lengths: list[int] = []
    try:
        with opener(path, "rt") as f:  # type: ignore[arg-type]
            while len(lengths) < max_reads:
                header = f.readline()
                if not header:
                    break
                seq = f.readline().strip()
                f.readline()
                f.readline()
                if seq:
                    lengths.append(len(seq))
    except OSError:
        return 150
    return int(sum(lengths) / len(lengths)) if lengths else 150


def _guess_platform(read_length: int) -> str:
    if read_length >= 1000:
        return "nanopore_or_pacbio"
    if read_length >= 200:
        return "illumina_long_insert"
    return "illumina"


def _sample_id_from_name(name: str) -> str:
    base = re.sub(r"\.(fastq|fq)(\.gz)?$", "", name, flags=re.I)
    base = re.sub(r"(_R1|_R2|_1|_2)$", "", base, flags=re.I)
    return base


def _pair_key(name: str) -> str:
    """Normalize R1/R2 tokens so mates share the same key."""
    return R1_RE.sub("_RX", R2_RE.sub("_RX", name), count=1)


def discover_samples(input_path: str | Path) -> list[SampleMeta]:
    path = Path(input_path).expanduser().resolve()
    if path.is_file():
        files = [path] if _is_fastq(path) else []
    else:
        files = sorted(p for p in path.iterdir() if p.is_file() and _is_fastq(p))

    if not files:
        raise FileNotFoundError(f"No FASTQ files found under: {path}")

    for f in files:
        if not _gzip_ok(f):
            raise ValueError(f"Invalid gzip header: {f}")

    used: set[Path] = set()
    samples: list[SampleMeta] = []

    r1_candidates = [f for f in files if R1_RE.search(f.name) and not R2_RE.search(f.name)]
    for r1 in r1_candidates:
        if r1 in used:
            continue
        key = _pair_key(r1.name)
        r2 = next(
            (
                f
                for f in files
                if f not in used and f != r1 and R2_RE.search(f.name) and _pair_key(f.name) == key
            ),
            None,
        )
        used.add(r1)
        if r2:
            used.add(r2)
        read_len = _estimate_read_length(r1)
        samples.append(
            SampleMeta(
                sample_id=_sample_id_from_name(r1.name),
                r1=str(r1),
                r2=str(r2) if r2 else None,
                platform=_guess_platform(read_len),
                read_length_est=read_len,
                paired=bool(r2),
            )
        )

    for f in files:
        if f in used:
            continue
        read_len = _estimate_read_length(f)
        samples.append(
            SampleMeta(
                sample_id=_sample_id_from_name(f.name),
                r1=str(f),
                r2=None,
                platform=_guess_platform(read_len),
                read_length_est=read_len,
                paired=False,
            )
        )

    return samples


def parse_input(state: AgentState) -> dict:
    samples = discover_samples(state["input_path"])
    msg = f"Parsed {len(samples)} sample(s) from {state['input_path']}"
    return {
        "samples": samples,
        "messages": state.get("messages", []) + [msg],
    }
