"""Step-level intermediate result cache — skip completed swarm nodes on resume."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# Artifact keys that indicate a node already produced durable outputs
_AGENT_MARKERS: dict[str, list[str]] = {
    "qc": ["qc_host", "quality_report_html"],
    "qc_host": ["qc_host"],
    "taxonomy": ["taxonomy", "taxonomy_profile"],
    "assembly": ["assembly", "mag_summary"],
    "functional": ["functional", "functional_profile"],
    "function": ["functional", "functional_profile"],
    "statistics": ["statistics"],
    "stats": ["statistics"],
    "visualization": ["visualization"],
}


def _config_fingerprint(state: dict[str, Any]) -> str:
    """Stable hash of execution-relevant config (images, threads, assembler prefs)."""
    cfg = state.get("config") or {}
    cache_cfg = cfg.get("cache") or {}
    if not cache_cfg.get("include_config_hash", True):
        return "nocfg"
    slim = {
        "mode": state.get("mode"),
        "threads": (cfg.get("linux") or {}).get("threads") or (cfg.get("docker") or {}).get("threads"),
        "memory_gb": (cfg.get("linux") or {}).get("memory_gb"),
        "images": sorted((cfg.get("docker") or {}).get("images") or {}),
        "assembler": (cfg.get("pipeline") or {}).get("default_assembler"),
        "engine": (cfg.get("execution") or {}).get("engine"),
    }
    return hashlib.sha256(json.dumps(slim, sort_keys=True).encode()).hexdigest()[:10]


def cache_key(node: dict[str, Any], state: dict[str, Any]) -> str:
    payload = {
        "id": node.get("id"),
        "agent": node.get("agent"),
        "tools": node.get("tools") or [],
        "params": node.get("params") or {},
        "mode": state.get("mode"),
        "n_samples": len(state.get("samples") or []),
        "sample_ids": [s.get("sample_id") for s in (state.get("samples") or [])],
        "input_path": state.get("input_path"),
        "config_fp": _config_fingerprint(state),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


class StepCache:
    def __init__(self, outdir: str | Path, enabled: bool = True):
        self.enabled = enabled
        self.root = Path(outdir) / "cache" / "steps"
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"
        self._index: dict[str, Any] = {}
        if self.index_path.exists():
            try:
                self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._index = {}

    def flush(self) -> None:
        self.index_path.write_text(json.dumps(self._index, indent=2, ensure_ascii=False), encoding="utf-8")

    def lookup(self, node: dict[str, Any], state: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any] | None:
        """Return cached produced artifacts for node if valid, else None."""
        if not self.enabled:
            return None
        key = cache_key(node, state)
        entry = self._index.get(key)
        if not entry:
            # Heuristic: durable markers already on disk / in artifacts
            return self._heuristic_hit(node, artifacts)
        marker_paths = entry.get("marker_paths") or []
        if marker_paths and not all(Path(p).exists() for p in marker_paths if p):
            return None
        cached_arts = entry.get("artifacts_slice") or {}
        if not cached_arts:
            return None
        return {"key": key, "artifacts_slice": cached_arts, "source": "index"}

    def _heuristic_hit(self, node: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any] | None:
        agent = node.get("agent") or ""
        markers = _AGENT_MARKERS.get(agent) or []
        if not markers:
            return None
        slice_: dict[str, Any] = {}
        for m in markers:
            if m in artifacts and artifacts[m]:
                slice_[m] = artifacts[m]
        # Also check common output files for this outdir-backed run
        if not slice_:
            return None
        # Require at least one marker that looks complete (non-empty dict/str)
        ok = False
        for v in slice_.values():
            if isinstance(v, dict) and v:
                ok = True
            if isinstance(v, str) and Path(v).exists():
                ok = True
        if not ok:
            return None
        return {"key": "heuristic", "artifacts_slice": slice_, "source": "heuristic"}

    def store(
        self,
        node: dict[str, Any],
        state: dict[str, Any],
        produced: dict[str, Any],
        outdir: Path,
    ) -> str:
        key = cache_key(node, state)
        marker_paths: list[str] = []
        arts_slice: dict[str, Any] = {}
        for k, v in produced.items():
            if k in {"messages", "agent_messages", "errors"}:
                continue
            arts_slice[k] = v
            if isinstance(v, str) and (v.endswith((".tsv", ".html", ".json", ".md", ".txt")) or "/outdir" in v):
                marker_paths.append(v)
            if isinstance(v, dict):
                for vv in v.values():
                    if isinstance(vv, str) and Path(vv).suffix in {".tsv", ".html", ".json", ".fastq", ".fa", ".fasta"}:
                        marker_paths.append(vv)
        # Persist slice JSON for audit
        slice_path = self.root / f"{node.get('id', 'node')}_{key}.json"
        slice_path.write_text(json.dumps(arts_slice, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        self._index[key] = {
            "node_id": node.get("id"),
            "agent": node.get("agent"),
            "marker_paths": marker_paths[:40],
            "artifacts_slice": _lightweight_slice(arts_slice),
            "slice_file": str(slice_path),
        }
        self.flush()
        return key


def _lightweight_slice(arts: dict[str, Any]) -> dict[str, Any]:
    """Keep structure but drop huge nested blobs for index.json."""
    out: dict[str, Any] = {}
    for k, v in arts.items():
        if isinstance(v, dict) and len(json.dumps(v, default=str)) > 50_000:
            out[k] = {"_cached_ref": True, "n_keys": len(v)}
        else:
            out[k] = v
    return out


def merge_cached_into_artifacts(artifacts: dict[str, Any], slice_: dict[str, Any]) -> dict[str, Any]:
    arts = dict(artifacts)
    for k, v in slice_.items():
        if isinstance(v, dict) and isinstance(arts.get(k), dict) and not v.get("_cached_ref"):
            arts[k] = {**arts.get(k, {}), **v}
        elif not (isinstance(v, dict) and v.get("_cached_ref")):
            arts[k] = v
    return arts
