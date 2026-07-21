> English: [USAGE.md](USAGE.md)

# 使用指南（v0.23）

架构与设计见 [ARCHITECTURE.zh-CN.md](ARCHITECTURE.zh-CN.md)；内存 ≥256 GB 的 Linux 部署见 [DEPLOY_LINUX.zh-CN.md](DEPLOY_LINUX.zh-CN.md)。

## CLI

入口：`meta-agent`。

### `run`

| Option | Default | Description |
|--------|---------|-------------|
| `-i / --input` | required | FASTQ 文件或目录 |
| `-o / --outdir` | `./results` | 输出目录 |
| `-m / --mode` | `mock` | `mock` \| `local` \| `conda` \| `docker` \| `apptainer` |
| `-q / --query` | generic analysis phrase | 驱动 Router 意图与领域 |
| `--metadata` | none | 含 `sample_id,group` 的 TSV/CSV（差异分析推荐） |
| `-c / --config` | `config/default.yaml` | YAML 覆盖配置 |
| `-y / --yes` | false | 自动确认 HITL（含 Plan Validator 提示） |

```bash
# Demo (recommended: one-click grouped data; or bash scripts/reproduce_demo.sh)
meta-agent run -i examples/demo_data/fastq --metadata examples/demo_data/metadata.tsv \
  -o ./results/demo --mode mock --yes \
  -q "IBD vs healthy gut microbiome biomarker discovery"

# Minimal single-sample fixture (CI)
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut microbiome biomarker discovery"

# Real data
meta-agent run -i /data/fastq -o /data/out --mode docker \
  -c config/default.yaml --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

### `serve` / `version`

```bash
meta-agent serve --host 127.0.0.1 --port 8000
meta-agent version
```

异步 HITL（Web/API）：

```bash
# Start analysis and pause at gates
curl -X POST http://127.0.0.1:8000/analyze -H 'Content-Type: application/json' \
  -d '{"input_path":"tests/fixtures/fastq","outdir":"./results/async1","mode":"mock","hitl_mode":"async"}'

# List pending confirmation gates
curl "http://127.0.0.1:8000/runs/<run_id>/hitl?outdir=./results/async1"

# Submit decisions and resume
curl -X POST http://127.0.0.1:8000/runs/<run_id>/hitl/decide \
  -H 'Content-Type: application/json' \
  -d '{"outdir":"./results/async1","decisions":[{"id":"confirm_report_publish","key":"B"}],"resume":true}'
```

Web UI（分析 + Chat）：

```bash
meta-agent serve --host 127.0.0.1 --port 8000
open http://127.0.0.1:8000/ui
```

Chat（有据问答；可选绑定已完成 run 的 outdir / 项目 Memory）：

```bash
curl -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -d '{"question":"Why is Faecalibacterium reduced in IBD?","outdir":"./results"}'
```

容器编排层：

```bash
# Orchestration layer (image does not include database/; mount reference DBs as needed)
docker compose up --build
# Production mount of host DBs: META_REF=/ref/databases docker compose up --build
```

差异分析 R 导出（DESeq2 / MaAsLin2 / ANCOM-BC）：运行后见 `biomarkers/r_export/`；可选设置 `statistics.try_run_r: true`。

环境变量：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`（可选）。

## 配置（`config/default.yaml`）

| Section | Role |
|---------|------|
| `execution.engine` | `langgraph`（默认）\| `nextflow` \| `snakemake`；后两者消费 Agent 写出的参数 |
| `execution.skip_swarm_on_engine_ok` | NF/SMK 成功时跳过双跑 swarm |
| `sandbox.*` / `apptainer.sif_dir` | 容器后端；HPC SIF 缓存目录 |
| `docker.*` / `linux.*` | BioContainers 覆盖、线程/内存/GPU、`scheduler` |
| `cache.per_sample_assembly` | 复用 `outdir/<sample>/assembly/` 下的组装产物 |
| `cache.include_config_hash` | 配置变更时使步骤缓存失效 |
| `routing.*` | gLM / 双路径 / ε-greedy |
| `paths.*` | 数据库、宿主索引、gLM 权重/命令 |
| `pipeline.*` | 组装与分类工具列表 |
| `validation.*` | QC 阈值；contract / Plan Validator 硬失败 |
| `interpretation.*` | 抗幻觉：`require_grounding`、`require_evidence_chain` |
| `summary.*` | 摘要驱动上下文：`enabled`、`max_llm_chars` |
| `reproducibility.*` | `auto_export`、`seed` |
| `visualization.*` | `default_q`、`lite`（按需加载）、`max_inline_biomarkers` |
| `cache.enabled` | LangGraph 步骤缓存 |
| `rag.*` | `keyword` \| `semantic`；`authority_dbs` |
| `literature.*` | PubMed / Europe PMC / OpenAlex 等 |
| `statistics.*` | `demo_mode`、`lefse_like`、`ancom_like` |
| `hitl.auto_confirm` | CI/`--yes` 可设为 `true`；交互式生产应使用 `false` |
| `hitl.mode` | `sync`（CLI Prompt）\| `async`（API 落盘暂停） |
| `hitl.require_assembly_confirm` | Assembly 提交前需人工确认 |
| `hitl.require_otu_filter_confirm` | 稀有 OTU/ASV 阈值需人工确认 |
| `hitl.require_database_confirm` | 非 mock 且参考库路径缺失时确认 |
| `hitl.require_report_publish_confirm` | 报告可分享 / 草稿 / 暂缓 |
| `hitl.require_self_heal_confirm` | 确认高风险自愈（mock / loosen_qc / 降低置信度 / 降级组装器） |
| `hitl.default_self_heal` | `B`=仅安全（推荐）· `A`=全部 · `C`=拒绝 |
| `hitl.default_report_publish` | `A` 可分享 · `B` 草稿 · `C` 暂缓 |
| `statistics.min_prevalence` / `min_rel_abundance` | HITL 确认后的特征过滤阈值 |
| `project.*` | 宿主 / 坐标系 / 领域 Memory 字段 |
| `report.manuscript_template` | 手稿模板名 |
| `pi.max_replans` | PI 重规划次数 |

参考库**构建步骤与目录约定**：[database/README.md](../database/README.md)（Kraken2 / MetaPhlAn / GTDB / CARD 逐步说明）；辅助脚本 `scripts/build_databases.sh`。

## 元数据示例

```tsv
sample_id	group
S1	IBD
S2	Control
```

## 主要输出

| Path | Description |
|------|-------------|
| `final_report.html` | 完整报告（内嵌多面板 Plotly 图） |
| `bio_reasoning.md` · `.json` · `_audit.json` | 规划前生物学推理 + CoT 引用审计 |
| `resource_estimate.json` | 预估运行时间/内存/磁盘与断点续跑提示 |
| `cache/steps/` | Swarm 中间缓存（checkpoint 续跑） |
| `taxonomy_interpretation.md` | 基于分类的污染 / 富集假说 |
| `functional_interpretation.md` | 功能通路机制说明 |
| `interactive_dashboard.html` | 交互仪表盘（显著分类群 q-slider） |
| `quality_report.html` / `quality_status.json` | QC |
| `taxonomy_profile.tsv` | 分类谱 |
| `diversity_analysis/` | Alpha/Beta 多样性、属水平矩阵 |
| `biomarkers/` | 差异生物标志物表 |
| `evidence/claims.md` | 抗幻觉证据链 |
| `evidence/evidence_table.md` | 文献证据表 |
| `context/pipeline_summary.json` | 供 LLM 上下文的统计摘要 |
| `planner/planner_plan.md` | Planner：实验设计与完整流程 |
| `executor/submit.{slurm,pbs,sge}` · `job.k8s.yaml` | Executor：多调度器提交规格 |
| `executor/cluster_sense.json` · `resource_allocation.json` | 队列压力与受限 CPU/内存/GPU |
| `outdir/<sample>/assembly/checkpoint.json` | MEGAHIT/SPAdes 中间 checkpoint |
| `critic/qc_critic.md` · `bio_qc_chain.json` | QC 链：CheckM2 HQ、未分类、Q20/Q30 |
| `evidence/grounded_interp.md` | 表绑定解读（物种/p/q/效应仅来自程序表） |
| `hitl/critical_gates.json` · `CRITICAL_GATES.md` | 关键 HITL 审计 |
| `hitl/async/session.json` · `state.json` · `AWAITING.md` | 异步审批会话（API 续跑） |
| `reasoning/chain.md` · `chain.jsonl` | 跨 Agent 决策审计 |
| `literature_report.md` | 结构化文献报告 |
| `visualization/figure_legends.md` | 图注（Figure 1–4） |
| `report/HELD.md` | HITL 暂缓发布报告时的占位 |
| `diversity_analysis/otu_asv_filter.json` | 稀有特征剔除摘要 |
| `reporter/biological_report.md` | Reporter：多样性与通路解读 |
| `workflow/params.yaml` · `params.json` | 校验后的引擎参数（Schema + 任务图） |
| `workflow/ENGINE_README.md` | Nextflow/Snakemake 启动说明 |
| `workflow/reproducible.nf` · `.smk` · `seeds.json` | 可重复导出 |
| `workflow/generated.nf` · `.smk` | 规划阶段 RAG 草稿 |
| `reproducibility/run_manifest.json` | 运行清单 + CWL |
| `router_decision.json` | 意图与领域路由 |
| `tool_specialist/tool_commands.md` | 工具命令 |
| `plan_validation.json` | 计划校验 / 追问 |
| `xai/feature_importance.md` | 生物标志物归因 |
| `report/manuscript/` | 手稿章节草稿 |
| `logs/events.jsonl` | 执行事件 |

## 故障排查

| Symptom | Remedy |
|---------|--------|
| Plan Validator 要求宿主基因组 | 设置 `paths.host_index` 或 `project.host_genome_version`，或使用 mock/`--yes` |
| 无分组 → 无法做差异分析 | 提供 `--metadata`，或设置 `statistics.demo_mode: true` |
| HITL 卡住 | `--yes` / `hitl.auto_confirm: true`；API 使用 `hitl_mode=async` 再 `/hitl/decide` |
| 缺少宿主库 / ARM 错误 | `--mode docker`；自愈可能切换容器 / 钉死 amd64 |
| OOM / exit 137 | 自愈提高内存 / 降低线程；**仅在组装节点将组装器降级为 MEGAHIT**；见 [SELF_HEAL.zh-CN.md](SELF_HEAL.zh-CN.md) |
| 担心自愈“假修复” | 默认 `hitl.require_self_heal_confirm` + `default_self_heal: B` 会扣留高风险动作 |
| 病毒工具未安装 | Specialist 仍会写出命令；安装工具或保持 mock |
| 原始 stderr 刷屏 | 用户看到自愈摘要；详情在 `artifacts.errors` / `logs/` |
