"""Async HITL API + database/report publish gates (v0.20)."""

from pathlib import Path

from fastapi.testclient import TestClient

from metagenomic_agent.agents.hitl import _apply_action, hitl_checkpoint
from metagenomic_agent.agents.hitl_async import apply_decisions_to_state, load_session, write_awaiting_session
from metagenomic_agent.agents.hitl_gates import (
    build_database_gate,
    build_report_publish_gate,
    register_critical_gates,
)
from metagenomic_agent.api.server import app
from metagenomic_agent.graph import _route_after_hitl


def test_database_gate_skipped_in_mock():
    state = {
        "mode": "mock",
        "config": {"hitl": {"require_database_confirm": True}, "paths": {}},
    }
    assert build_database_gate(state) is None


def test_database_gate_when_missing_paths():
    state = {
        "mode": "local",
        "config": {
            "hitl": {"require_database_confirm": True, "database_confirm_only_when_missing": True},
            "paths": {"kraken2_db": "", "gtdb": "<unset>"},
        },
    }
    gate = build_database_gate(state)
    assert gate is not None
    assert gate["id"] == "confirm_databases"
    assert gate["gate"] == "database_download"


def test_report_publish_gate_and_hold():
    gate = build_report_publish_gate({"config": {"hitl": {"require_report_publish_confirm": True}}})
    assert gate["id"] == "confirm_report_publish"
    assert gate["default"] == "B"

    out = _apply_action(
        {"config": {}, "artifacts": {}, "messages": [], "dag": []},
        "hold_report",
    )
    assert out["artifacts"]["hold_report"] is True
    assert out["artifacts"]["report_publish_confirmed"] is False


def test_register_includes_report_gate():
    state = {
        "mode": "mock",
        "dag": [],
        "config": {"hitl": {"require_report_publish_confirm": True}},
        "artifacts": {"hitl_options": []},
        "hitl_pending": [],
        "messages": [],
    }
    gated = register_critical_gates(state)
    ids = {o["id"] for o in gated["artifacts"]["hitl_options"]}
    assert "confirm_report_publish" in ids


def test_async_park_and_route(tmp_path: Path):
    state = {
        "outdir": str(tmp_path),
        "run_id": "abcd1234",
        "user_query": "test",
        "input_path": "/tmp/x",
        "mode": "mock",
        "config": {"hitl": {"mode": "async"}},
        "hitl_auto_confirm": False,
        "hitl_async": True,
        "hitl_pending": ["note"],
        "artifacts": {
            "hitl_options": [
                {
                    "id": "confirm_report_publish",
                    "gate": "report_publish",
                    "question": "Publish?",
                    "choices": [
                        {"key": "A", "label": "yes", "action": "publish_report"},
                        {"key": "B", "label": "draft", "action": "draft_report_only"},
                    ],
                    "default": "B",
                }
            ]
        },
        "messages": [],
        "agent_messages": [],
        "dag": [],
        "samples": [],
        "tasks": [],
        "retry_count": 0,
        "max_retries": 2,
    }
    out = hitl_checkpoint(state)
    assert out["hitl_awaiting"] is True
    assert out["hitl_resolved"] is False
    assert (tmp_path / "hitl" / "async" / "session.json").exists()
    assert _route_after_hitl({**state, **out}) == "awaiting"

    sess = write_awaiting_session({**state, **out, "artifacts": out["artifacts"]})
    assert sess["status"] == "awaiting_hitl"

    patched = apply_decisions_to_state(
        {**state, "artifacts": out["artifacts"]},
        [{"id": "confirm_report_publish", "key": "A"}],
    )
    assert patched["hitl_resolved"] is True
    assert patched["hitl_awaiting"] is False
    assert patched["artifacts"]["report_shareable"] is True
    assert load_session(tmp_path)["status"] == "decided"


def test_api_async_analyze_parks(tmp_path: Path):
    # Minimal input file so /analyze accepts path
    fq = tmp_path / "s_R1.fastq"
    fq.write_text("@r1\nACGT\n+\nIIII\n", encoding="utf-8")
    outdir = tmp_path / "out"
    client = TestClient(app)
    resp = client.post(
        "/analyze",
        json={
            "input_path": str(fq),
            "outdir": str(outdir),
            "mode": "mock",
            "query": "mock IBD analysis",
            "hitl_mode": "async",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "awaiting_hitl"
    assert body["hitl_awaiting"] is True
    assert body["run_id"]
    run_id = body["run_id"]

    hitl = client.get(f"/runs/{run_id}/hitl", params={"outdir": str(outdir)})
    assert hitl.status_code == 200
    opts = hitl.json()["options"]
    assert opts

    decisions = [{"id": o["id"], "key": o.get("default") or "A"} for o in opts]
    decide = client.post(
        f"/runs/{run_id}/hitl/decide",
        json={"outdir": str(outdir), "decisions": decisions, "resume": True},
    )
    assert decide.status_code == 200, decide.text
    assert decide.json()["status"] == "completed"
    assert decide.json()["report_path"]
