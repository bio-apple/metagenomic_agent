from pathlib import Path

from metagenomic_agent.input.parser import discover_samples

from conftest import write_tiny_fastq


def test_discover_paired_samples(tmp_path: Path):
    write_tiny_fastq(tmp_path / "S1_R1.fastq")
    write_tiny_fastq(tmp_path / "S1_R2.fastq")
    write_tiny_fastq(tmp_path / "S2_1.fastq")
    write_tiny_fastq(tmp_path / "S2_2.fastq")
    samples = discover_samples(tmp_path)
    assert len(samples) == 2
    assert all(s["paired"] for s in samples)
    ids = {s["sample_id"] for s in samples}
    assert "S1" in ids
    assert "S2" in ids


def test_estimate_platform_illumina(tmp_path: Path):
    write_tiny_fastq(tmp_path / "solo.fastq", length=150)
    samples = discover_samples(tmp_path / "solo.fastq")
    assert samples[0]["platform"] == "illumina"
    assert samples[0]["paired"] is False
