# 使用指南（v0.20）

架构见 [ARCHITECTURE.md](ARCHITECTURE.md)，能力对照见 [ROADMAP.md](ROADMAP.md)。

## CLI

入口：`meta-agent`。

### `run`

| 选项 | 默认 | 说明 |
|------|------|------|
| `-i / --input` | 必填 | FASTQ 文件或目录 |
| `-o / --outdir` | `./results` | 输出目录 |
| `-m / --mode` | `mock` | `mock` \| `local` \| `conda` \| `docker` \| `apptainer` |
| `-q / --query` | 通用分析句 | 驱动 Router 意图与领域 |
| `--metadata` | 无 | `sample_id,group` 的 TSV/CSV（差异分析推荐） |
| `-c / --config` | `config/default.yaml` | YAML 覆盖 |
| `-y / --yes` | false | 自动确认 HITL（含 Plan Validator 追问） |

```bash
# 演示
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut microbiome biomarker discovery"

# 真实数据
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
# 启动分析并在门控处暂停
curl -X POST http://127.0.0.1:8000/analyze -H 'Content-Type: application/json' \
  -d '{"input_path":"tests/fixtures/fastq","outdir":"./results/async1","mode":"mock","hitl_mode":"async"}'

# 查看待确认门控
curl "http://127.0.0.1:8000/runs/<run_id>/hitl?outdir=./results/async1"

# 提交决策并续跑
curl -X POST http://127.0.0.1:8000/runs/<run_id>/hitl/decide \
  -H 'Content-Type: application/json' \
  -d '{"outdir":"./results/async1","decisions":[{"id":"confirm_report_publish","key":"B"}],"resume":true}'
```

环境变量：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`（可选）。

## 配置（`config/default.yaml`）

| 段 | 作用 |
|------|------|
| `execution.engine` | `langgraph`（默认）\| `nextflow` \| `snakemake`；后两者读 Agent 写出的 params |
| `execution.skip_swarm_on_engine_ok` | NF/SMK 成功时跳过双跑 swarm |
| `sandbox.*` / `apptainer.sif_dir` | 容器后端；HPC SIF 缓存目录 |
| `docker.*` / `linux.*` | BioContainers 覆盖、线程/内存/GPU、`scheduler` |
| `cache.per_sample_assembly` | 复用 `outdir/<sample>/assembly/` 拼接产物 |
| `cache.include_config_hash` | 配置变更时使步骤缓存失效 |
| `routing.*` | gLM / 双路 / ε-greedy |
| `paths.*` | 数据库、宿主 index、gLM 权重/命令 |
| `pipeline.*` | 组装、分类工具列表 |
| `validation.*` | 质控阈值、契约/Plan Validator 硬失败 |
| `interpretation.*` | 抗幻觉：`require_grounding`、`require_evidence_chain` |
| `summary.*` | 摘要驱动上下文：`enabled`、`max_llm_chars` |
| `reproducibility.*` | `auto_export`、`seed` |
| `visualization.*` | `default_q`、`lite`（按需加载）、`max_inline_biomarkers` |
| `cache.enabled` | LangGraph 步骤缓存 |
| `rag.*` | `keyword` \| `semantic`；`authority_dbs` |
| `literature.*` | PubMed / Europe PMC / OpenAlex 等 |
| `statistics.*` | `demo_mode`、`lefse_like`、`ancom_like` |
| `hitl.auto_confirm` | CI/`--yes` 可 `true`；交互生产建议 `false` |
| `hitl.mode` | `sync`（CLI Prompt）\| `async`（API 落盘暂停） |
| `hitl.require_assembly_confirm` | Assembly 提交前人工确认 |
| `hitl.require_otu_filter_confirm` | 极低频 OTU/ASV 阈值人工确认 |
| `hitl.require_database_confirm` | 非 mock 且参考库路径缺失时确认 |
| `hitl.require_report_publish_confirm` | 报告可分享 / 草稿 / 暂缓 |
| `hitl.default_report_publish` | `A` 可分享 · `B` 草稿 · `C` 暂缓 |
| `statistics.min_prevalence` / `min_rel_abundance` | HITL 确认后的特征过滤阈值 |
| `project.*` | 宿主/坐标系统/领域等 Memory 字段 |
| `report.manuscript_template` | 手稿模板名 |
| `pi.max_replans` | PI 复盘次数 |

参考库目录说明见 [database/README.md](../database/README.md)。

## 元数据示例

```tsv
sample_id	group
S1	IBD
S2	Control
```

## 主要产物

| 路径 | 说明 |
|------|------|
| `final_report.html` | 总报告（内嵌 Plotly 多图） |
| `bio_reasoning.md` · `.json` · `_audit.json` | 规划前生物学推理 + CoT 引用审计 |
| `resource_estimate.json` | 预估耗时/内存/磁盘与 resume 提示 |
| `cache/steps/` | Swarm 中间结果缓存（断点续跑） |
| `taxonomy_interpretation.md` | 分类结果污染/富集假设 |
| `functional_interpretation.md` | 功能通路机制笔记 |
| `interactive_dashboard.html` | 交互仪表盘（q 滑块筛选显著菌） |
| `quality_report.html` / `quality_status.json` | QC |
| `taxonomy_profile.tsv` | 分类轮廓 |
| `diversity_analysis/` | Alpha/Beta、属矩阵 |
| `biomarkers/` | 差异标志物表 |
| `evidence/claims.md` | 抗幻觉证据链 |
| `evidence/evidence_table.md` | 文献证据表 |
| `context/pipeline_summary.json` | LLM 用统计摘要 |
| `planner/planner_plan.md` | Planner：实验设计与整体 Pipeline |
| `executor/submit.{slurm,pbs,sge}` · `job.k8s.yaml` | Executor：多调度器提交规格 |
| `executor/cluster_sense.json` · `resource_allocation.json` | 队列压力与封顶后的 CPU/内存/GPU |
| `outdir/<sample>/assembly/checkpoint.json` | MEGAHIT/SPAdes 中间 Checkpoint |
| `critic/qc_critic.md` · `bio_qc_chain.json` | QC 链：CheckM2 HQ、unclassified、Q20/Q30 |
| `evidence/grounded_interp.md` | 表绑定解读（物种/p/q/effect 仅来自程序表） |
| `hitl/critical_gates.json` · `CRITICAL_GATES.md` | 关键 HITL 审计 |
| `hitl/async/session.json` · `state.json` · `AWAITING.md` | 异步审批会话（API resume） |
| `report/HELD.md` | HITL 选择暂缓报告时的占位说明 |
| `diversity_analysis/otu_asv_filter.json` | 低频特征剔除摘要 |
| `reporter/biological_report.md` | Reporter：多样性与通路解读 |
| `workflow/params.yaml` · `params.json` | 校验后的引擎参数（Schema + 任务图） |
| `workflow/ENGINE_README.md` | Nextflow/Snakemake 启动说明 |
| `workflow/reproducible.nf` · `.smk` · `seeds.json` | 可复现导出 |
| `workflow/generated.nf` · `.smk` | 规划期 RAG 草稿 |
| `reproducibility/run_manifest.json` | 运行清单 + CWL |
| `router_decision.json` | 意图与领域路由 |
| `tool_specialist/tool_commands.md` | 工具命令 |
| `plan_validation.json` | 方案校验 / 追问 |
| `xai/feature_importance.md` | 标志物归因 |
| `report/manuscript/` | 投稿分节草稿 |
| `logs/events.jsonl` | 执行事件 |

## 排障

| 现象 | 处理 |
|------|------|
| Plan Validator 追问宿主基因组 | 设 `paths.host_index` 或 `project.host_genome_version`，或 mock/`--yes` |
| 缺分组无法差异分析 | `--metadata`，或 `statistics.demo_mode: true` |
| HITL 卡住 | `--yes` / `hitl.auto_confirm: true`；API 用 `hitl_mode=async` 后 `/hitl/decide` |
| 宿主机缺库 / ARM 报错 | `--mode docker`；自愈可切容器 / 钉 amd64 |
| OOM / exit 137 | 自愈降 threads/memory，组装降级 MEGAHIT |
| 病毒工具未安装 | Specialist 仍写命令；安装工具或保持 mock |
| 原始 stderr 刷屏 | 用户侧看自愈摘要；细节在 `artifacts.errors` / `logs/` |
