"""Tool Specialist Agent — precise per-tool commands and parameters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metagenomic_agent.knowledge.domain_kb import load_tool_domain_kb, recommend_tools, tool_command
from metagenomic_agent.messaging import append_msg, emit
from metagenomic_agent.skills.contracts import Severity
from metagenomic_agent.skills.registry import get_skill


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

    # Sample/upstream stub for skill pre-checks (planning-time)
    sample0 = (state.get("samples") or [{}])[0] if state.get("samples") else {"r1": "<r1>", "r2": "<r2>"}
    upstream_stub = {
        "r1": sample0.get("r1") or "<r1>",
        "clean_r1": "results/clean_R1.fastq",
        "contigs": "<contigs.fa>",
        "bins_dir": "<bins_dir>",
    }

    specs: list[dict[str, Any]] = []
    contract_notes: list[dict[str, Any]] = []
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

        skill = get_skill(name)
        skill_meta = None
        if skill:
            from metagenomic_agent.skills.contracts import check_preconditions

            # Planning-time: only flag hard structural issues; placeholders allowed in mock
            viol = check_preconditions(skill, sample0, upstream_stub)
            # Downgrade path-missing on placeholders to info at plan time
            soft = []
            for v in viol:
                if state.get("mode") == "mock" or "<" in str(upstream_stub.get(v.details.get("key", ""), "")):
                    soft.append(
                        {
                            "skill": skill.name,
                            "check": v.check,
                            "message": v.message,
                            "severity": "info",
                        }
                    )
                else:
                    soft.append(
                        {
                            "skill": skill.name,
                            "check": v.check,
                            "message": v.message,
                            "severity": v.severity.value if isinstance(v.severity, Severity) else str(v.severity),
                        }
                    )
            skill_meta = {
                "name": skill.name,
                "description": skill.description,
                "input_required": skill.input_contract.required_artifacts,
                "output_required": skill.output_contract.required_outputs,
                "pre_check": soft,
                "execution_policy": "skill_contract_not_freeform_cli",
            }
            contract_notes.extend(soft)

        specs.append(
            {
                "tool": name,
                "status": meta.get("status", "active" if skill else "unregistered_skill"),
                "specialty": meta.get("specialty"),
                "params": {k: params[k] for k in param_keys if k in params},
                "command": cmd,
                "missing_required": missing_req if state.get("mode") != "mock" else [],
                "notes": meta.get("strengths"),
                "skill_contract": skill_meta,
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

    payload = {
        "specialists": specs,
        "n_tools": len(specs),
        "skill_contract_notes": contract_notes,
        "policy": "commands_are_templates_execution_must_honor_skill_io_contracts",
    }
    out = Path(state["outdir"]) / "tool_specialist"
    out.mkdir(parents=True, exist_ok=True)
    (out / "tool_commands.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Tool Specialist Commands", "", "> Skills use I/O contracts; CLI templates are not free-form LLM shell.", ""]
    for s in specs:
        lines.append(f"## {s['tool']}")
        if s.get("skill_contract"):
            sc = s["skill_contract"]
            lines.append(
                f"- Contract in=`{sc.get('input_required')}` out=`{sc.get('output_required')}`"
            )
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
