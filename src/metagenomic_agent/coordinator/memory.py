"""Context memory: project profile + TF-IDF vector index over history/summaries."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_\-]{2,}|[\u4e00-\u9fff]+", (text or "").lower())


class ContextMemory:
    def __init__(self, workdir: str | Path):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.path = self.workdir / "context.json"
        self.index_path = self.workdir / "memory_index.json"
        self._data: dict[str, Any] = {
            "project": {},
            "samples": [],
            "artifacts": {},
            "pipeline_summary": {},
            "history": [],
            "dag": [],
            "run_seed": None,
            "memory_docs": [],
        }
        if self.path.exists():
            loaded = json.loads(self.path.read_text())
            self._data.update(loaded)

    def set_project_profile(self, profile: dict[str, Any]) -> None:
        self._data["project"] = {**(self._data.get("project") or {}), **profile}
        self.flush()

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key in {"artifacts"} and isinstance(value, dict):
                self._data.setdefault("artifacts", {}).update(value)
            elif key == "project" and isinstance(value, dict):
                self._data["project"] = {**(self._data.get("project") or {}), **value}
            elif key == "pipeline_summary" and isinstance(value, dict):
                self._data["pipeline_summary"] = value
                self.index_document("pipeline_summary", json.dumps(value, ensure_ascii=False)[:4000])
            else:
                self._data[key] = value
        self.flush()

    def llm_safe_view(self) -> dict[str, Any]:
        """Return a context payload without raw sequence paths' file contents."""
        return {
            "project": self.project,
            "pipeline_summary": self._data.get("pipeline_summary")
            or (self._data.get("artifacts") or {}).get("pipeline_summary")
            or {},
            "run_seed": self._data.get("run_seed"),
            "dag": self._data.get("dag") or [],
            "history_tail": (self._data.get("history") or [])[-20:],
        }

    def append_history(self, event: str) -> None:
        self._data.setdefault("history", []).append(event)
        self.index_document(f"history:{len(self._data['history'])}", event)
        self.flush()

    def index_document(self, doc_id: str, text: str) -> None:
        """Upsert a document into the in-memory doc store (rebuilt on retrieve)."""
        docs = list(self._data.get("memory_docs") or [])
        docs = [d for d in docs if d.get("id") != doc_id]
        docs.append({"id": doc_id, "text": text[:8000]})
        # Cap store
        self._data["memory_docs"] = docs[-200:]
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        docs = list(self._data.get("memory_docs") or [])
        # Also fold history + summary if not already docs
        if self._data.get("pipeline_summary") and not any(d.get("id") == "pipeline_summary" for d in docs):
            docs.append(
                {
                    "id": "pipeline_summary",
                    "text": json.dumps(self._data["pipeline_summary"], ensure_ascii=False)[:4000],
                }
            )
        for i, h in enumerate((self._data.get("history") or [])[-50:]):
            did = f"hist:{i}"
            if not any(d.get("id") == did for d in docs):
                docs.append({"id": did, "text": str(h)})

        df: Counter[str] = Counter()
        tokenized: list[list[str]] = []
        for d in docs:
            toks = _tokenize(d.get("text") or "")
            tokenized.append(toks)
            df.update(set(toks))
        n = max(len(docs), 1)
        idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
        vectors: list[dict[str, float]] = []
        for toks in tokenized:
            tf = Counter(toks)
            denom = max(sum(tf.values()), 1)
            vec = {t: (tf[t] / denom) * idf.get(t, 0.0) for t in tf}
            # L2 normalize
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            vectors.append({t: v / norm for t, v in vec.items()})
        payload = {"docs": docs, "idf": idf, "vectors": vectors}
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """TF-IDF cosine retrieval over project memory (vector-lite project Memory)."""
        if not self.index_path.exists():
            self._rebuild_index()
        if not self.index_path.exists():
            return []
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        docs = payload.get("docs") or []
        idf = payload.get("idf") or {}
        vectors = payload.get("vectors") or []
        q_tf = Counter(_tokenize(query))
        denom = max(sum(q_tf.values()), 1)
        q_vec = {t: (q_tf[t] / denom) * float(idf.get(t, 1.0)) for t in q_tf}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        q_vec = {t: v / q_norm for t, v in q_vec.items()}

        scored: list[dict[str, Any]] = []
        for doc, vec in zip(docs, vectors):
            score = sum(q_vec.get(t, 0.0) * float(w) for t, w in vec.items())
            if score > 0:
                scored.append(
                    {
                        "id": doc.get("id"),
                        "score": round(score, 4),
                        "text": (doc.get("text") or "")[:500],
                    }
                )
        scored.sort(key=lambda x: -x["score"])
        return scored[:top_k]

    def flush(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def project(self) -> dict[str, Any]:
        return dict(self._data.get("project") or {})
