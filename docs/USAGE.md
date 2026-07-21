# 使用指南（v0.9）

## CLI

入口：`meta-agent`。

### `meta-agent run`

| 选项 | 默认 | 说明 |
|------|------|------|
| `-i / --input` | 必填 | FASTQ 文件或目录 |
| `-o / --outdir` | `./results` | 输出目录 |
| `-m / --mode` | `mock` | `mock` \| `local` \| `conda` \| `docker` \| `apptainer` |
| `-q / --query` | 通用分析句 | 驱动 Router 意图与领域路由 |
| `--metadata` | 无 | `sample_id,group` 的 TSV/CSV（差异分析推荐） |
| `-c / --config` | `config/default.yaml` | YAML 覆盖 |
| `-y / --yes` | false | 强制自动确认 HITL（含 Plan Validator 追问） |

```bash
# 演示
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut microbiome biomarker discovery"

# 真实数据（建议提供分组）
meta-agent run -i /data/fastq -o /data/out --mode local \
  -c config/default.yaml --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

### `meta-agent serve` / `version`

```bash
meta-agent serve --host 127.0.0.1 --port 8000   # GET /health  POST /analyze
meta-agent version
```

## 配置要点（`config/default.yaml`）

| 段 | 作用 |
|------|------|
| `sandbox.*` | 容器后端、`prefer_container`、`platform`、mock 回退 |
| `docker.platform` | 默认 `linux/amd64`（biocontainers / Apple Silicon） |
| `routing.*` | gLM / 双路 / ε-greedy |
| `paths.*` | 数据库、`glm_weights`、`glm_inference_cmd`、`host_index` |
| `pipeline.*` | 组装开关、分类工具列表 |
| `validation.plan_validator_hard_fail` | 领域约束缺失时是否硬阻断 |
| `validation.contract_hard_fail` | 契约 ERROR 时是否中止 swarm |
| `literature.*` | PubMed / Europe PMC / OpenAlex / Semantic Scholar |
| `statistics.lefse_like` / `ancom_like` | 近似差异方法 |
| `rag.mode` | `keyword` \| `semantic` |
| `pi.max_replans` | PI 复盘次数 |
| `project.*` | Memory：`host`、`host_genome_version`、`coordinate_system`、`target_domain` |
| `hitl.auto_confirm` | CI/演示可 `true`；生产交互建议 `false` |

环境变量：`OPENAI_API_KEY`、`OPENAI_BASE_URL`。

## 多智能体相关产物

| 文件 | 说明 |
|------|------|
| `router_decision.json` | 主意图、领域、推荐工具 |
| `tool_specialist/tool_commands.md` | 各工具命令模板 |
| `plan_validation.json` | 是否通过；缺失元数据追问列表 |
| `workflow/generated.nf` | Nextflow 草稿（RAG） |
| `xai/feature_importance.md` | 标志物驱动解释 |

## 元数据示例

```tsv
sample_id	group
S1	IBD
S2	Control
```

## 排障

| 现象 | 处理 |
|------|------|
| Plan Validator 追问宿主基因组 | 设置 `paths.host_index` 或 `project.host_genome_version`，或 mock/`--yes` |
| 缺分组无法做差异 | 提供 `--metadata`，或 `statistics.demo_mode: true` |
| HITL 卡住 | `--yes` 或 `hitl.auto_confirm: true` |
| 病毒工具未安装 | Specialist 仍会写出命令；安装 ViWrap/PhaBOX 或保持 mock |
| 宿主机缺库 / ARM 架构报错 | 改用 `--mode docker`；自愈会尝试 `switch_to_container` / `pin_platform_amd64` |
| OOM / exit 137 | 自愈降低 threads/memory，组装降级 MEGAHIT |
| 看到原始 stderr 刷屏 | 正常路径只展示 `user_message`；完整日志在 `artifacts.errors` |

架构见 [ARCHITECTURE.md](ARCHITECTURE.md)。
