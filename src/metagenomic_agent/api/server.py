"""HTTP API for Metagenomic Research Agent."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from metagenomic_agent import __version__
from metagenomic_agent.config_loader import load_config
from metagenomic_agent.graph import resume_pipeline, run_pipeline
from metagenomic_agent.state import AgentState

app = FastAPI(
    title="Metagenomic Research Agent API",
    description="Autonomous AI agent system for end-to-end metagenomic analysis",
    version=__version__,
)


class AnalyzeRequest(BaseModel):
    input_path: str = Field(..., description="FASTQ file or directory")
    outdir: str = Field("./results", description="Output directory")
    query: str = Field(
        "Analyze shotgun metagenomic samples from IBD patients and healthy controls. "
        "Identify microbial biomarkers."
    )
    mode: Literal["mock", "local", "conda", "docker", "apptainer"] = "mock"
    metadata_path: Optional[str] = None
    config_path: Optional[str] = None
    hitl_mode: Literal["auto", "sync", "async"] = Field(
        "auto",
        description="auto=auto-confirm gates; async=park for Web approval; sync=CLI prompts (not for API)",
    )


class AnalyzeResponse(BaseModel):
    report_path: Optional[str]
    critic_passed: bool
    messages: list[str]
    artifacts_keys: list[str]
    paths: dict[str, Any]
    run_id: Optional[str] = None
    status: str = "completed"
    hitl_awaiting: bool = False
    hitl_session: Optional[dict[str, Any]] = None


class HitlDecision(BaseModel):
    id: str = Field(..., description="Gate option id, e.g. confirm_assembly")
    key: str = Field(..., description="Choice key A/B/C/…")
    action: Optional[str] = None


class HitlDecideRequest(BaseModel):
    outdir: str = Field(..., description="Run output directory (contains hitl/async/)")
    decisions: list[HitlDecision]
    resume: bool = Field(True, description="Continue pipeline after applying decisions")


class HitlDecideResponse(BaseModel):
    status: str
    run_id: Optional[str] = None
    report_path: Optional[str] = None
    messages: list[str] = Field(default_factory=list)
    hitl_awaiting: bool = False


def _build_initial(req: AnalyzeRequest, outdir: Path, input_path: Path, cfg: dict[str, Any]) -> AgentState:
    hitl_mode = req.hitl_mode
    if hitl_mode == "auto":
        cfg.setdefault("hitl", {})["auto_confirm"] = True
        cfg["hitl"]["mode"] = "sync"
        hitl_auto = True
        hitl_async = False
    elif hitl_mode == "async":
        cfg.setdefault("hitl", {})["auto_confirm"] = False
        cfg["hitl"]["mode"] = "async"
        hitl_auto = False
        hitl_async = True
    else:
        cfg.setdefault("hitl", {})["auto_confirm"] = False
        cfg["hitl"]["mode"] = "sync"
        hitl_auto = False
        hitl_async = False

    return {
        "user_query": req.query,
        "input_path": str(input_path.resolve()),
        "outdir": str(outdir.resolve()),
        "mode": req.mode,
        "config": cfg,
        "samples": [],
        "metadata_path": str(Path(req.metadata_path).resolve()) if req.metadata_path else None,
        "tasks": [],
        "dag": [],
        "artifacts": {},
        "messages": [],
        "agent_messages": [],
        "validation": None,
        "critic": None,
        "literature": None,
        "statistics": None,
        "retry_count": 0,
        "max_retries": int(cfg.get("max_retries", 2)),
        "hitl_pending": [],
        "hitl_auto_confirm": hitl_auto,
        "hitl_async": hitl_async,
        "hitl_awaiting": False,
        "hitl_resolved": False,
        "report_path": None,
        "error": None,
        "run_id": str(uuid.uuid4())[:8],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    input_path = Path(req.input_path).expanduser()
    if not input_path.exists():
        raise HTTPException(status_code=400, detail=f"input_path not found: {req.input_path}")

    outdir = Path(req.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(req.config_path, overrides={"mode": req.mode})
    initial = _build_initial(req, outdir, input_path, cfg)

    try:
        final = run_pipeline(initial)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    paths_file = outdir / "paths.json"
    paths: dict[str, Any] = {}
    if paths_file.exists():
        paths = json.loads(paths_file.read_text())

    awaiting = bool(final.get("hitl_awaiting"))
    session = (final.get("artifacts") or {}).get("hitl_async_session")
    critic = final.get("critic") or {}
    return AnalyzeResponse(
        report_path=final.get("report_path"),
        critic_passed=bool(critic.get("passed", True)) if not awaiting else True,
        messages=list(final.get("messages", []))[-30:],
        artifacts_keys=sorted(final.get("artifacts", {}).keys()),
        paths=paths,
        run_id=final.get("run_id") or initial.get("run_id"),
        status="awaiting_hitl" if awaiting else "completed",
        hitl_awaiting=awaiting,
        hitl_session=session,
    )


@app.get("/runs/{run_id}/hitl")
def get_hitl(run_id: str, outdir: Optional[str] = None) -> dict[str, Any]:
    """Fetch pending async HITL session. Prefer ?outdir=…; else scan common roots."""
    from metagenomic_agent.agents.hitl_async import load_session, session_dir

    candidates: list[Path] = []
    if outdir:
        candidates.append(Path(outdir).expanduser())
    else:
        # Best-effort: look under ./results and cwd for matching run_id
        for root in (Path("results"), Path(".")):
            if not root.exists():
                continue
            for sess in root.rglob("hitl/async/session.json"):
                candidates.append(sess.parent.parent.parent)

    for base in candidates:
        sess = load_session(base)
        if not sess:
            continue
        if sess.get("run_id") == run_id or outdir:
            return {
                "run_id": sess.get("run_id"),
                "status": sess.get("status"),
                "outdir": str(base),
                "pending": sess.get("pending") or [],
                "options": sess.get("options") or [],
                "session_path": str(session_dir(base) / "session.json"),
            }

    raise HTTPException(status_code=404, detail=f"HITL session not found for run_id={run_id}")


@app.post("/runs/{run_id}/hitl/decide", response_model=HitlDecideResponse)
def decide_hitl(run_id: str, req: HitlDecideRequest) -> HitlDecideResponse:
    """Apply async HITL decisions and optionally resume the pipeline."""
    from metagenomic_agent.agents.hitl_async import apply_decisions_to_state, load_session, load_state

    outdir = Path(req.outdir).expanduser()
    sess = load_session(outdir)
    if not sess:
        raise HTTPException(status_code=404, detail=f"No HITL session under {outdir}")
    if sess.get("run_id") and sess["run_id"] != run_id:
        raise HTTPException(
            status_code=400,
            detail=f"run_id mismatch: path has {sess.get('run_id')}, request {run_id}",
        )
    if sess.get("status") == "decided" and not req.resume:
        return HitlDecideResponse(status="already_decided", run_id=run_id, messages=["Session already decided"])

    state = load_state(outdir)
    if not state:
        raise HTTPException(status_code=404, detail="Missing hitl/async/state.json")

    decisions = [d.model_dump(exclude_none=True) for d in req.decisions]
    patched = apply_decisions_to_state(state, decisions)
    if patched.get("error"):
        raise HTTPException(status_code=400, detail=str(patched["error"]))

    if not req.resume:
        return HitlDecideResponse(
            status="decided",
            run_id=run_id,
            messages=list(patched.get("messages") or [])[-20:],
            hitl_awaiting=False,
        )

    try:
        final = resume_pipeline(patched)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    awaiting = bool(final.get("hitl_awaiting"))
    return HitlDecideResponse(
        status="awaiting_hitl" if awaiting else "completed",
        run_id=run_id,
        report_path=final.get("report_path"),
        messages=list(final.get("messages") or [])[-30:],
        hitl_awaiting=awaiting,
    )


class ChatRequest(BaseModel):
    question: str = Field(..., description="Metagenomics / study question")
    outdir: Optional[str] = Field(None, description="Optional completed run outdir for grounded context")
    top_k: int = Field(5, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    grounded_hits: list[dict[str, Any]]
    literature_excerpt: Optional[str] = None
    biomarkers: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = (
        "Answers are RAG-grounded and not clinical advice; verify against tables and PMIDs."
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """Lightweight ChatCopilot: hybrid RAG + optional run artifacts (no free-form hallucination)."""
    from metagenomic_agent.rag import retrieve_multi
    from metagenomic_agent.rag.authority import authority_context_block, ground_taxon

    hits_map = retrieve_multi(req.question, top_k_per_db=2, mode="hybrid")
    flat = [h for hits in hits_map.values() for h in hits]
    flat.sort(key=lambda x: -float(x.get("score") or 0))
    flat = flat[: req.top_k]

    biomarkers: list[dict[str, Any]] = []
    lit_excerpt = None
    if req.outdir:
        out = Path(req.outdir).expanduser()
        bio = out / "biomarkers" / "biomarkers.tsv"
        if bio.exists():
            import csv

            with bio.open(encoding="utf-8") as fh:
                for row in csv.DictReader(fh, delimiter="\t"):
                    biomarkers.append(dict(row))
                    if len(biomarkers) >= 8:
                        break
        for cand in (
            out / "literature_report.md",
            out / "literature_summary" / "literature_report.md",
        ):
            if cand.exists():
                lit_excerpt = cand.read_text(encoding="utf-8")[:2500]
                break

    # Build grounded answer from authority + hits (no unconstrained LLM required)
    lines = [f"Q: {req.question}", "", "Grounded context:"]
    for h in flat[:5]:
        lines.append(
            f"- [{h.get('database')}] {h.get('name') or h.get('id')}: "
            f"{(h.get('notes') or h.get('pathway') or '')[:160]}"
        )
    # Try to ground first token that looks like a taxon
    tokens = [t for t in req.question.replace(",", " ").split() if t[:1].isupper() and len(t) > 3]
    for t in tokens[:3]:
        g = ground_taxon(t)
        if g.get("grounded"):
            lines.append(f"- Taxon `{t}` → canonical `{g.get('canonical_name')}`")
            ctx = authority_context_block(t)
            if ctx:
                lines.append(ctx[:400])
    if biomarkers:
        lines.append("")
        lines.append("From run biomarkers:")
        for b in biomarkers[:5]:
            lines.append(
                f"- {b.get('genus')}: {b.get('direction')} p={b.get('p_value')} q={b.get('q_value')}"
            )
    if not flat and not biomarkers:
        lines.append("- No curated hits; refine the question or mount fuller database/ RAG dumps.")

    return ChatResponse(
        answer="\n".join(lines),
        grounded_hits=flat,
        literature_excerpt=lit_excerpt,
        biomarkers=biomarkers,
    )
