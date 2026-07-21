"""Code Agent — generate + sandbox-execute small Python analysis scripts (no free shell)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.reasoning_log import log_decision

SAFE_TEMPLATE = '''\
#!/usr/bin/env python3
"""Auto-generated analysis snippet — read-only tables under OUTDIR."""
from __future__ import annotations
import csv, json
from pathlib import Path

OUTDIR = Path({outdir!r})
mat = OUTDIR / "diversity_analysis" / "genus_matrix.tsv"
bio = OUTDIR / "biomarkers" / "biomarkers.tsv"
summary = {{"n_matrix_lines": 0, "n_biomarkers": 0, "top": []}}
if mat.exists():
    lines = mat.read_text(encoding="utf-8").splitlines()
    summary["n_matrix_lines"] = max(0, len(lines) - 1)
if bio.exists():
    rows = list(csv.DictReader(bio.open(encoding="utf-8"), delimiter="\\t"))
    summary["n_biomarkers"] = len(rows)
    summary["top"] = [{{"genus": r.get("genus"), "q": r.get("q_value")}} for r in rows[:5]]
out = OUTDIR / "code_agent" / "sandbox_result.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
'''


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    outdir = Path(state["outdir"])
    code_dir = outdir / "code_agent"
    code_dir.mkdir(parents=True, exist_ok=True)
    script_path = code_dir / "analyze_tables.py"
    script = SAFE_TEMPLATE.format(outdir=str(outdir.resolve()))
    script_path.write_text(script, encoding="utf-8")

    # Optional user/LLM snippet (whitelisted: must only read OUTDIR tables)
    custom = ((node or {}).get("params") or {}).get("python_snippet")
    if custom and "import os" not in custom and "subprocess" not in custom and "open('/" not in custom:
        custom_path = code_dir / "custom_snippet.py"
        custom_path.write_text(
            "from pathlib import Path\nimport json, csv\n"
            f"OUTDIR = Path({str(outdir.resolve())!r})\n" + custom,
            encoding="utf-8",
        )
        run_path = custom_path
    else:
        run_path = script_path

    result: dict[str, Any] = {"script": str(run_path), "ok": False}
    try:
        proc = subprocess.run(
            [sys.executable, str(run_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(code_dir),
            check=False,
        )
        result["returncode"] = proc.returncode
        result["stdout"] = (proc.stdout or "")[-2000:]
        result["stderr"] = (proc.stderr or "")[-1000:]
        result["ok"] = proc.returncode == 0
        sandbox_json = code_dir / "sandbox_result.json"
        if sandbox_json.exists():
            result["summary"] = json.loads(sandbox_json.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)

    # Also emit a tiny R stub for MaAsLin handoff (not executed here)
    r_stub = code_dir / "plot_biomarkers.R"
    r_stub.write_text(
        "# Optional R viz — run manually\n"
        "# read biomarkers/biomarkers.tsv and ggplot volcano\n",
        encoding="utf-8",
    )
    result["r_stub"] = str(r_stub)

    (code_dir / "code_agent.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    reason = log_decision(
        state,
        "code",
        "Sandbox Python table analysis",
        f"ok={result.get('ok')}; script={run_path.name}",
    )
    arts = {**(state.get("artifacts") or {}), **(reason.get("artifacts") or {}), "code_agent": result}
    return {
        "artifacts": arts,
        "messages": state.get("messages", [])
        + [f"Code Agent: sandbox ok={result.get('ok')} → {code_dir}"],
    }
