# 使用指南

面向 **v0.15**。架构见 [ARCHITECTURE.md](ARCHITECTURE.md)，论文表述见 [METHODS.md](METHODS.md)。

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
meta-agent serve --host 127.0.0.1 --port 8000   # GET /health  POST /analyze
meta-agent version
```

环境变量：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`（可选）。

## 配置（`config/default.yaml`）

| 段 | 作用 |
|------|------|
| `execution.engine` | `langgraph`（默认）\| `nextflow` \| `snakemake`；后两者读 Agent 写出的 params |
| `sandbox.*` | 容器后端、`prefer_container`、`platform`、mock 回退 |
| `docker.*` / `linux.*` | 镜像平台、线程、内存 |
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
| `hitl.auto_confirm` | CI 可 `true`；交互生产建议 `false` |
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
| HITL 卡住 | `--yes` 或 `hitl.auto_confirm: true` |
| 宿主机缺库 / ARM 报错 | `--mode docker`；自愈可切容器 / 钉 amd64 |
| OOM / exit 137 | 自愈降 threads/memory，组装降级 MEGAHIT |
| 病毒工具未安装 | Specialist 仍写命令；安装工具或保持 mock |
| 原始 stderr 刷屏 | 用户侧看自愈摘要；细节在 `artifacts.errors` / `logs/` |
