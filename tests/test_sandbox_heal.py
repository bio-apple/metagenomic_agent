"""Sandbox isolation + self-heal robustness tests."""

from metagenomic_agent.execution.self_heal import apply_self_heal, classify_from_errors, summarize_heal_for_user
from metagenomic_agent.tools.linux_runner import classify_error
from metagenomic_agent.tools.sandbox import ToolCallRequest, friendly_error_message, sandbox_from_config


def test_classify_arch_and_library():
    assert classify_error(1, "exec format error") == "arch_mismatch"
    assert classify_error(1, "error while loading shared libraries: libstdc++.so.6") == "missing_library"


def test_friendly_error_hides_raw_dump():
    msg, hints = friendly_error_message("oom", "Killed\nlong stack " * 50, "metaspades")
    assert "memory" in msg.lower() or "oom" in msg.lower() or "137" in msg
    assert hints
    assert "long stack" not in msg  # should not dump full stderr body repeatedly


def test_sandbox_mock_tool_call():
    ex = sandbox_from_config({"mode": "mock", "sandbox": {"prefer_container": True}})
    resp = ex.execute(ToolCallRequest(tool="kraken2", argv=["kraken2", "--help"]))
    assert resp.ok
    assert resp.backend == "mock"


def test_self_heal_switches_to_container_on_missing_lib():
    actions = classify_from_errors(
        [{"classified": "missing_library", "error": "libstdc++ missing", "user_message": "Missing shared libraries"}]
    )
    assert "switch_to_container" in actions
    dag = [{"id": "qc", "agent": "qc", "tools": ["fastp"], "params": {}, "depends_on": [], "status": "failed"}]
    new_dag, patch = apply_self_heal(dag, actions, {"mode": "local", "linux": {"threads": 8, "memory_gb": 32}})
    assert patch.get("mode") == "docker" or patch.get("sandbox", {}).get("backend") == "docker"
    assert "prefer_container" in str(new_dag[0].get("params"))


def test_self_heal_pin_amd64():
    actions = classify_from_errors([{"classified": "arch_mismatch", "stderr": "exec format error"}])
    assert "pin_platform_amd64" in actions
    _, patch = apply_self_heal([], actions, {})
    assert patch.get("sandbox", {}).get("platform") == "linux/amd64"


def test_summarize_heal_for_user():
    s = summarize_heal_for_user(
        ["reduce_memory", "switch_to_container"],
        [{"classified": "oom", "user_message": "out of memory"}],
    )
    assert "self-heal" in s.lower()
    assert "oom" in s or "memory" in s.lower()
