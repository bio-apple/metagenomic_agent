from pathlib import Path

from metagenomic_agent.agents import critic_agent, statistics_agent
from metagenomic_agent.input.metadata import apply_groups, load_sample_groups
from conftest import write_tiny_fastq


def test_metadata_groups(tmp_path: Path):
    meta = tmp_path / "meta.tsv"
    meta.write_text("sample_id\tgroup\nA\tIBD\nB\tControl\n")
    assert load_sample_groups(meta) == {"A": "IBD", "B": "Control"}
    samples = [{"sample_id": "A"}, {"sample_id": "B"}]
    assert apply_groups(samples, load_sample_groups(meta))[0]["group"] == "IBD"


def test_statistics_and_critic(tmp_path: Path):
    write_tiny_fastq(tmp_path / "x.fastq")
    tax = tmp_path / "taxonomy_profile.tsv"
    tax.write_text(
        "sample\tgenus\trelative_abundance\ttool\n"
        "S1\tFaecalibacterium\t0.05\tkraken2\n"
        "S1\tEscherichia\t0.20\tkraken2\n"
        "S2\tFaecalibacterium\t0.25\tkraken2\n"
        "S2\tEscherichia\t0.03\tkraken2\n"
    )
    state = {
        "user_query": "IBD biomarkers",
        "outdir": str(tmp_path / "out"),
        "mode": "mock",
        "config": {},
        "samples": [
            {"sample_id": "S1", "group": "IBD", "r1": "x", "paired": False, "platform": "illumina", "read_length_est": 150},
            {"sample_id": "S2", "group": "Control", "r1": "x", "paired": False, "platform": "illumina", "read_length_est": 150},
        ],
        "artifacts": {
            "taxonomy_profile": str(tax),
            "taxonomy": {
                "S1": {"top_genera": ["Escherichia", "Faecalibacterium"], "classification_rate": 0.7},
                "S2": {"top_genera": ["Faecalibacterium", "Escherichia"], "classification_rate": 0.7},
            },
            "qc_host": {
                "S1": {"read_retention": 0.9, "host_fraction": 0.1, "Q30": 95, "status": "PASS"},
                "S2": {"read_retention": 0.9, "host_fraction": 0.1, "Q30": 95, "status": "PASS"},
            },
        },
        "messages": [],
    }
    stats_out = statistics_agent.run(state)
    state["artifacts"]["statistics"] = stats_out["statistics"]
    state["statistics"] = stats_out["statistics"]
    assert Path(stats_out["statistics"]["biomarkers"]).exists()
    critic_out = critic_agent.run(state)
    assert "critic" in critic_out
