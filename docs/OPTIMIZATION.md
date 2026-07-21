# 优化差距闭环（v0.21）

对照 Copilot 建议书的短板补齐状态。

| 项 | 状态 | 产物 / 入口 |
|----|------|-------------|
| 统一推理链 | **Done** | `reasoning/chain.jsonl` · `chain.md` |
| literature_report | **Done** | `literature_report.md` |
| Hybrid RAG | **Done** | `rag.mode: hybrid` + `database/` 目录契约 |
| Dockerfile / compose | **Done** | 根目录 `Dockerfile` · `docker-compose.yml` |
| Figure legends | **Done** | `visualization/figure_legends.md` |
| CONCOCT / RGI / DeepARG / VirSorter2 / CheckV | **Done** | mock + 容器镜像 pin；`pipeline.enable_arg/virus` |
| Chat Copilot（轻量） | **Done** | `POST /chat`（RAG 接地，非完整 Web UI） |

仍属长期项：全量 CAMI、向量 Memory、完整 Web/React UI、DESeq2/MaAsLin2 原生调用。
