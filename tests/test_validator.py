from metagenomic_agent.validators.biological import validate_biological
from metagenomic_agent.validators.recovery import apply_recovery, plan_recovery
from metagenomic_agent.validators.technical import validate_technical
import pytest


def _state(**kwargs):
    base = {
        "user_query": "分析肠道宏基因组",
        "samples": [{"sample_id": "S1", "r1": "x", "paired": True, "platform": "illumina", "read_length_est": 150}],
        "artifacts": {
            "qc_host": {"S1": {"read_retention": 0.9, "host_fraction": 0.1}},
            "taxonomy": {
                "S1": {
                    "kraken2_abundance": __file__,  # existing path
                    "top_genera": ["Bacteroides", "Prevotella"],
                }
            },
        },
        "config": {
            "validation": {
                "min_read_retention": 0.3,
                "max_host_fraction": 0.95,
                "require_gut_markers": True,
                "gut_marker_genera": ["Bacteroides", "Faecalibacterium"],
            }
        },
        "dag": [
            {
                "id": "taxonomy",
                "agent": "taxonomy",
                "tools": ["kraken2"],
                "params": {"confidence": 0.05},
                "depends_on": ["qc"],
                "status": "done",
            }
        ],
    }
    base.update(kwargs)
    return base


def test_technical_pass():
    assert validate_technical(_state())["ok"] is True


def test_technical_fail_low_retention():
    st = _state()
    st["artifacts"]["qc_host"]["S1"]["read_retention"] = 0.1
    assert validate_technical(st)["ok"] is False


def test_biological_pass():
    assert validate_biological(_state())["ok"] is True


def test_recovery_lowers_confidence():
    st = _state()
    st["artifacts"]["taxonomy"]["S1"]["top_genera"] = ["Unknown"]
    bio = validate_biological(st)
    assert bio["ok"] is False
    actions = plan_recovery(st, {"ok": True, "samples": {}}, bio)
    assert "lower_kraken_confidence" in actions
    new_dag = apply_recovery(st["dag"], actions)
    assert new_dag[0]["params"]["confidence"] == pytest.approx(0.03)
