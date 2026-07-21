from metagenomic_agent.execution.self_heal import apply_self_heal, classify_from_errors
from metagenomic_agent.knowledge import rag
from metagenomic_agent.tools.linux_runner import classify_error


def test_classify_oom():
    assert classify_error(137, "") == "oom"
    assert classify_error(1, "cannot allocate memory") == "oom"


def test_self_heal_downgrades_assembler():
    dag = [
        {
            "id": "assembly_binning",
            "agent": "assembly",
            "tools": ["metaspades", "metabat2"],
            "params": {"assembler": "metaspades"},
            "depends_on": [],
            "status": "failed",
        }
    ]
    actions = classify_from_errors([{"returncode": 137, "error": "Killed", "classified": "oom"}])
    assert "downgrade_assembler" in actions
    new_dag, patch = apply_self_heal(dag, actions, {"linux": {"threads": 16, "memory_gb": 64}})
    assert new_dag[0]["params"]["assembler"] == "megahit"
    assert patch["linux"]["threads"] == 8
    assert patch["linux"]["memory_gb"] == 32


def test_rag_akkermansia():
    hits = rag.retrieve("Akkermansia muciniphila")
    assert hits
    assert "mucin" in hits[0]["mechanism"].lower() or "Mucin" in hits[0]["mechanism"]
