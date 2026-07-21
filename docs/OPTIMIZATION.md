# 优化差距闭环（v0.22）

对照 Copilot 建议书的短板补齐状态。

| 项 | 状态 | 产物 / 入口 |
|----|------|-------------|
| 统一推理链 | **Done** | `reasoning/chain.jsonl` · `chain.md` |
| literature_report | **Done** | `literature_report.md` |
| Hybrid RAG | **Done** | `rag.mode: hybrid` + `database/` 目录契约 |
| Dockerfile / compose | **Done** | 根目录 `Dockerfile` · `docker-compose.yml` |
| Figure legends | **Done** | `visualization/figure_legends.md` |
| CONCOCT / RGI / DeepARG / VirSorter2 / CheckV | **Done** | mock + 容器镜像 pin |
| Chat Copilot | **Done** | `POST /chat` |
| CAMI toy 基准 | **Done** | `evaluation/cami_toy.*` · `run_benchmark_suite` |
| 项目 Memory 向量检索 | **Done** | `ContextMemory.retrieve`（TF-IDF） |
| Web UI | **Done** | `GET /` · `GET /ui` 单页 Copilot |
| DESeq2 / MaAsLin2 / ANCOM-BC | **Done** | `biomarkers/r_export/` + 可选 `try_run_r` |

说明：CAMI 为 toy gold（非全量 OPAMI/AMBER）；Memory 为本地 TF-IDF（非外部向量库）；R 原生工具需本机安装对应包，否则保留脚本 + Python *‑like 回退。
