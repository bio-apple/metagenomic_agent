from pathlib import Path

import pytest


def write_tiny_fastq(path: Path, n: int = 4, length: int = 50) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seq = "ACGT" * (length // 4)
    qual = "I" * length
    lines = []
    for i in range(n):
        lines.extend([f"@read{i}", seq, "+", qual])
    path.write_text("\n".join(lines) + "\n")


@pytest.fixture
def paired_fastq_dir(tmp_path: Path) -> Path:
    write_tiny_fastq(tmp_path / "gut_R1.fastq")
    write_tiny_fastq(tmp_path / "gut_R2.fastq")
    return tmp_path
