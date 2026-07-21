"""Skill registry — standardized bioinformatics tool skills with contracts."""

from __future__ import annotations

from metagenomic_agent.skills.contracts import InputContract, OutputContract, Skill

SKILLS: dict[str, Skill] = {
    "fastp": Skill(
        name="fastp",
        description="Adapter trimming and quality filtering",
        input_contract=InputContract(required_artifacts=["r1"]),
        output_contract=OutputContract(
            required_outputs=["clean_r1", "status"],
            min_read_retention=0.3,
        ),
        tags=["qc"],
    ),
    "filter_host": Skill(
        name="filter_host",
        description="Host DNA removal (Bowtie2/Kneaddata vs HG38)",
        input_contract=InputContract(required_artifacts=["clean_r1"]),
        output_contract=OutputContract(required_outputs=["nonhost_r1"]),
        tags=["qc", "host"],
    ),
    "kraken2": Skill(
        name="kraken2",
        description="k-mer taxonomic classification + Bracken",
        input_contract=InputContract(required_artifacts=["r1"], max_read_length=2000),
        output_contract=OutputContract(
            required_outputs=["kraken2_abundance"],
            min_classification_rate=0.05,
        ),
        tags=["taxonomy", "short_read"],
    ),
    "metaphlan": Skill(
        name="metaphlan",
        description="Marker-gene taxonomic profiling",
        input_contract=InputContract(required_artifacts=["r1"]),
        output_contract=OutputContract(required_outputs=["metaphlan_abundance"]),
        tags=["taxonomy"],
    ),
    "microcafe": Skill(
        name="microcafe",
        description="Genomic language model taxonomy (long-read friendly)",
        input_contract=InputContract(required_artifacts=["r1"], min_read_length=500),
        output_contract=OutputContract(
            required_outputs=["glm_abundance", "top_genera"],
            min_classification_rate=0.1,
        ),
        tags=["taxonomy", "glm", "long_read"],
    ),
    "microrag": Skill(
        name="microrag",
        description="Retrieval-augmented genomic LM annotation",
        input_contract=InputContract(required_artifacts=["r1"]),
        output_contract=OutputContract(required_outputs=["glm_abundance"]),
        tags=["taxonomy", "glm"],
    ),
    "megahit": Skill(
        name="megahit",
        description="Fast metagenome assembly",
        input_contract=InputContract(required_artifacts=["r1"]),
        output_contract=OutputContract(required_outputs=["contigs"]),
        tags=["assembly"],
    ),
    "metaspades": Skill(
        name="metaspades",
        description="High-accuracy metagenome assembly",
        input_contract=InputContract(required_artifacts=["r1"], require_paired=True),
        output_contract=OutputContract(required_outputs=["contigs"]),
        tags=["assembly"],
    ),
    "metabat2": Skill(
        name="metabat2",
        description="Contig binning",
        input_contract=InputContract(required_artifacts=["contigs"]),
        output_contract=OutputContract(required_outputs=["bins_dir"]),
        tags=["binning"],
    ),
    "checkm2": Skill(
        name="checkm2",
        description="MAG completeness/contamination",
        input_contract=InputContract(required_artifacts=["bins_dir"]),
        output_contract=OutputContract(
            required_outputs=["checkm2"],
            min_completeness=50.0,
            max_contamination=10.0,
        ),
        tags=["mag_qc"],
    ),
    "diamond": Skill(
        name="diamond",
        description="Functional homology search",
        input_contract=InputContract(required_artifacts=["r1"]),
        output_contract=OutputContract(required_outputs=["functional_profile"]),
        tags=["function"],
    ),
}


def get_skill(name: str) -> Skill | None:
    return SKILLS.get(name)


def list_skills(tag: str | None = None) -> list[Skill]:
    skills = list(SKILLS.values())
    if tag:
        skills = [s for s in skills if tag in s.tags]
    return skills
