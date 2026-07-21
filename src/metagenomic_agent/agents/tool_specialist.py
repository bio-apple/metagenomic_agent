"""Tool Specialist Agent — precise per-tool commands and parameters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.domain_kb import load_tool_domain_kb, recommend_tools, tool_command
from metagenomic_agent.messaging import append_msg, emit


def run(state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = state.get("config") or {}
    paths = cfg.get("paths") or {}
    linux = cfg.get("linux") or {}
    router = (state.get("artifacts") or {}).get("router") or {}
    recs = router.get("recommended_tools") or recommend_tools(state.get("user_query") or "")

    dag_tools: list[str] = []
    for n in state.get("dag") or []:
        dag_tools.extend(n.get("tools") or [])

    tool_names = list(dict.fromkeys([r.get("tool") for r in recs if r.get("tool")] + dag_tools))
    kb_tools = load_tool_domain_kb().get("tools") or {}

    specs: list[dict[str, Any]] = []
    for name in tool_names:
        meta = kb_tools.get(name) or {}
        params = dict(meta.get("defaults") or {})
        params.update(
            {
                "threads": linux.get("threads", 8),
                "db": paths.get("kraken2_db")
                if name == "kraken2"
                else paths.get("metaphlan_db")
                or paths.get("diamond_db")
                or paths.get("glm_weights")
                or "<db>",
                "weights": paths.get("glm_weights") or "<weights>",
                "memory": min(float(linux.get("memory_gb", 64)) / 64.0, 0.9),
                "r1": "<r1>",
                "r2": "<r2>",
                "output": f"results/{name}",
                "report": f"results/{name}.report",
                "clean_r1": "results/clean_R1.fastq",
                "clean_r2": "results/clean_R2.fastq",
                "bowtie": f"results/{name}.bowtie2.bz2",
                "query": "<proteins.faa>",
                "contigs": "<contigs.fa>",
                "bins": "<bins_dir>",
                "input": "<input>",
                "reads_or_contigs": "<input>",
                "nproc": linux.get("threads", 8),
                "confidence": 0.05,
            }
        )
        required = list(meta.get("required_params") or [])
        missing_req = [p for p in required if not params.get(p) or str(params.get(p)).startswith("<")]
        cmd = tool_command(name, params)
        param_keys = set((meta.get("defaults") or {}).keys()) | set(required) | {"threads", "db"}
        specs.append(
            {
                "tool": name,
                "status": meta.get("status", "active"),
                "specialty": meta.get("specialty"),
                "params": {k: params[k] for k in param_keys if k in params},
                "command": cmd,
                "missing_required": missing_req if state.get("mode") != "mock" else [],
                "notes": meta.get("strengths"),
            }
        )

    dag = list(state.get("dag") or [])
    domains = router.get("domains") or []
    if "virus" in domains:
        for n in dag:
            if n.get("agent") == "taxonomy":
                tools = list(n.get("tools") or [])
                for vtool in ("viwrap", "phabox"):
                    if vtool not in tools:
                        tools.append(vtool)
                n["tools"] = tools
                n.setdefault("params", {})["virus_mode"] = True

    payload = {"specialists": specs, "n_tools": len(specs)}
    out = Path(state["outdir"]) / "tool_specialist"
    out.mkdir(parents=True, exist_ok=True)
    (out / "tool_commands.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Tool Specialist Commands", ""]
    for s in specs:
        lines.append(f"## {s['tool']}")
        lines.append(f"```bash\n{s.get('command')}\n```")
        if s.get("missing_required"):
            lines.append(f"- Missing required: {s['missing_required']}")
        lines.append("")
    (out / "tool_commands.md").write_text("\n".join(lines), encoding="utf-8")

    amsg = emit("tool_specialist", "plan_validator", "result", {"n_tools": len(specs)})
    return {
        "dag": dag,
        "artifacts": {**state.get("artifacts", {}), "tool_specialist": payload},
        "messages": state.get("messages", []) + [f"Tool Specialist prepared {len(specs)} tool command specs"],
        "agent_messages": append_msg(state.get("agent_messages"), amsg),
    }
