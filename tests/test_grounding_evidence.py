"""Anti-hallucination: authority grounding + evidence chains."""

from __future__ import annotations

import json
from pathlib import Path

from metagenomic_agent.knowledge.evidence_chain import build_claim, build_evidence_chains, write_evidence_chains
from metagenomic_agent.rag import retrieve
from metagenomic_agent.rag.authority import filter_ungrounded_taxa, ground_taxon
from metagenomic_agent.report.interpreter import interpret


def test_ground_known_taxon():
    g = ground_taxon("Faecalibacterium")
    assert g["grounded"] is True
    assert g.get("gtdb_id") or g.get("ncbi_taxid")
    assert g["database_ids"]


def test_reject_hallucinated_taxon():
    g = ground_taxon("Fakeobacter inventus xyzzy")
    assert g["grounded"] is False
    grounded, rejected = filter_ungrounded_taxa(["Faecalibacterium", "Fakeobacter inventus xyzzy"])
    assert any(r["taxon"] == "Faecalibacterium" for r in grounded)
    assert "Fakeobacter inventus xyzzy" in rejected


def test_uniprot_retrieve():
    hits = retrieve("uniprot", "Akkermansia")
    assert hits
    assert hits[0]["id"]


def test_evidence_chain_requires_stats(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "artifacts": {
            "statistics": {
                "biomarker_list": [
                    {
                        "genus": "Akkermansia",
                        "direction": "up",
                        "p_value": 0.012,
                        "q_value": 0.04,
                        "log2fc": 1.2,
                    }
                ],
                "groups": {},
            },
            "taxonomy": {},
        },
        "literature": {"entries": []},
    }
    claim = build_claim("Akkermansia", state, direction="up")
    assert claim["grounded"] is True
    assert claim["allowed"] is True
    assert claim["measurements"]["p_value"] == 0.012
    assert any(d["database"] in {"gtdb", "ncbi_taxonomy"} for d in claim["database_ids"])
    assert "p=" in (claim["statement"] or "")

    fake = build_claim("TotallyFakeGenus999", state)
    assert fake["grounded"] is False
    assert fake["allowed"] is False
    assert "Rejected" in (fake["statement"] or "") or "reject" in (fake["statement"] or "").lower()


def test_write_claims_and_interpret(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "user_query": "IBD biomarkers",
        "config": {"interpretation": {"require_grounding": True}},
        "artifacts": {
            "statistics": {
                "biomarker_list": [
                    {"genus": "Faecalibacterium", "direction": "down", "p_value": 0.001, "q_value": 0.01, "log2fc": -1.5},
                    {"genus": "Inventedium", "direction": "up", "p_value": 0.01, "q_value": 0.02, "log2fc": 2.0},
                ]
            },
            "taxonomy": {"S1": {"top_genera": ["Faecalibacterium", "Inventedium"]}},
        },
    }
    report = write_evidence_chains(state)
    assert (tmp_path / "evidence" / "claims.json").exists()
    assert report["n_rejected_ungrounded"] >= 1
    assert "Inventedium" in report["rejected_taxa"]
    text = interpret(state)
    assert "Evidence" in text or "evidence-chain" in text.lower() or "Evidence-Grounded" in text
    assert "Inventedium" in text or "Rejected" in text or "reject" in text.lower()
    data = json.loads((tmp_path / "evidence" / "claims.json").read_text(encoding="utf-8"))
    allowed = [c for c in data["claims"] if c["allowed"]]
    assert allowed
    assert allowed[0]["measurements"]["p_value"] is not None


def test_build_evidence_chains_empty_ok(tmp_path: Path):
    state = {"outdir": str(tmp_path), "artifacts": {"statistics": {}, "taxonomy": {}}}
    report = build_evidence_chains(state)
    assert report["n_candidates"] == 0
    assert report["claims"] == []
