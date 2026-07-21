"""Standard playbooks — mandatory step sequences that constrain LLM action space."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlaybookStep:
    name: str
    required_skills: list[str]
    optional_skills: list[str] = field(default_factory=list)
    agent: str = ""


@dataclass
class Playbook:
    name: str
    description: str
    steps: list[PlaybookStep]
    keywords: list[str] = field(default_factory=list)


PLAYBOOKS: dict[str, Playbook] = {
    "taxonomy_profiling": Playbook(
        name="taxonomy_profiling",
        description="Mandatory QC → host filter → taxonomic profiling",
        keywords=["taxonomy", "物种", "分类", "profile", "composition"],
        steps=[
            PlaybookStep("qc", ["fastp"], agent="qc"),
            PlaybookStep("host_removal", ["filter_host"], optional_skills=[], agent="qc"),
            PlaybookStep("taxonomy", ["kraken2"], optional_skills=["metaphlan", "microcafe"], agent="taxonomy"),
        ],
    ),
    "mag_recovery": Playbook(
        name="mag_recovery",
        description="Mandatory assembly → binning → CheckM2 → taxonomy of MAGs",
        keywords=["mag", "assembly", "组装", "分箱", "bin"],
        steps=[
            PlaybookStep("qc", ["fastp"], agent="qc"),
            PlaybookStep("assembly", ["megahit"], optional_skills=["metaspades"], agent="assembly"),
            PlaybookStep("binning", ["metabat2"], agent="assembly"),
            PlaybookStep("mag_qc", ["checkm2"], agent="assembly"),
        ],
    ),
    "ibd_biomarker": Playbook(
        name="ibd_biomarker",
        description="Taxonomy + differential markers + literature for IBD studies",
        keywords=["ibd", "biomarker", "标志", "炎症性肠病", "crohn", "colitis"],
        steps=[
            PlaybookStep("qc", ["fastp"], agent="qc"),
            PlaybookStep("taxonomy", ["kraken2", "metaphlan"], agent="taxonomy"),
            PlaybookStep("statistics", [], agent="statistics"),
            PlaybookStep("literature", [], agent="literature"),
        ],
    ),
}


def select_playbooks(query: str) -> list[Playbook]:
    q = query.lower()
    hit = [pb for pb in PLAYBOOKS.values() if any(k in q for k in pb.keywords)]
    if not hit:
        hit = [PLAYBOOKS["taxonomy_profiling"]]
    # Always ensure taxonomy playbook if only MAG selected without taxonomy keyword
    names = {p.name for p in hit}
    if "mag_recovery" in names and "taxonomy_profiling" not in names:
        hit.insert(0, PLAYBOOKS["taxonomy_profiling"])
    return hit


def playbook_required_skills(playbooks: list[Playbook]) -> list[str]:
    skills: list[str] = []
    for pb in playbooks:
        for step in pb.steps:
            skills.extend(step.required_skills)
    return list(dict.fromkeys(skills))


def enforce_playbook_on_dag(dag: list[dict[str, Any]], playbooks: list[Playbook]) -> tuple[list[dict[str, Any]], list[str]]:
    """Ensure mandatory skills appear in DAG tool lists; return notes."""
    notes: list[str] = []
    required = set(playbook_required_skills(playbooks))
    present: set[str] = set()
    for node in dag:
        present |= set(node.get("tools") or [])
    missing = sorted(required - present - {"fastp"})  # fastp may be implicit in qc
    # Inject missing taxonomy skills into taxonomy node
    for node in dag:
        if node.get("agent") == "taxonomy":
            tools = list(node.get("tools") or [])
            for sk in ("kraken2", "metaphlan"):
                if sk in required and sk not in tools:
                    tools.append(sk)
                    notes.append(f"Playbook injected skill '{sk}' into taxonomy")
            node["tools"] = tools
            node.setdefault("params", {})["tools"] = tools
        if node.get("agent") in {"qc", "qc_host"} and "fastp" in required:
            tools = list(node.get("tools") or [])
            if "fastp" not in tools:
                tools.insert(0, "fastp")
                notes.append("Playbook injected skill 'fastp' into QC")
            node["tools"] = tools
    if missing:
        notes.append(f"Playbook required skills not all present in DAG tools: {missing}")
    return dag, notes
