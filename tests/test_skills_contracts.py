"""Tests for Skill/Contract, gLM routing, and context-aware biology."""

from pathlib import Path

from metagenomic_agent.skills.bandit import EpsilonGreedyBandit
from metagenomic_agent.skills.contracts import check_postconditions, check_preconditions
from metagenomic_agent.skills.playbooks import select_playbooks
from metagenomic_agent.skills.registry import get_skill
from metagenomic_agent.skills.router import route_taxonomy_tools
from metagenomic_agent.validators.biological import validate_biological


def test_skill_contracts_fastp():
    skill = get_skill("fastp")
    assert skill
    pre = check_preconditions(skill, {"sample_id": "S", "r1": "/tmp/x.fastq", "paired": True}, {})
    # missing file may warn via path check — r1 key present so OK
    assert isinstance(pre, list)
    post = check_postconditions(skill, {"clean_r1": "x", "status": "PASS", "read_retention": 0.9})
    assert post == []


def test_playbook_ibd():
    pbs = select_playbooks("IBD biomarker discovery in gut metagenomes")
    names = {p.name for p in pbs}
    assert "ibd_biomarker" in names


def test_long_read_routes_to_glm():
    samples = [{"sample_id": "L1", "read_length_est": 8000, "paired": False, "r1": "x"}]
    routed = route_taxonomy_tools(samples, {"routing": {"enable_glm": True, "dual_path": False}}, outdir="/tmp")
    assert routed["features"]["is_long_read"] is True
    assert "microcafe" in routed["tools"] or "microrag" in routed["tools"]


def test_epsilon_greedy_learns(tmp_path: Path):
    path = tmp_path / "bandit.json"
    b = EpsilonGreedyBandit(epsilon=0.0, path=path)
    b.update("kraken2", success=True, quality=0.9, match=0.9)
    b.update("metaphlan", success=True, quality=0.2, match=0.2)
    assert b.select(["kraken2", "metaphlan"]) == "kraken2"


def test_context_aware_healthy_pathogen_warning():
    state = {
        "user_query": "Analyze healthy gut microbiome controls",
        "outdir": "/tmp",
        "config": {"validation": {"require_gut_markers": True, "gut_marker_genera": ["Bacteroides"]}},
        "samples": [{"sample_id": "H1"}],
        "artifacts": {
            "taxonomy": {"H1": {"top_genera": ["Bacteroides", "Salmonella"], "classification_rate": 0.6}}
        },
    }
    bio = validate_biological(state)
    assert bio["context"] == "healthy_gut"
    assert any("Salmonella" in w or "pathogen" in w.lower() or "concern" in w.lower() for w in bio["warnings"])
