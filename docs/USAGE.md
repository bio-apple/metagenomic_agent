# 使用指南（v0.7）

## CLI

入口：`meta-agent`（`pyproject.toml` → `[project.scripts]`）。

### `meta-agent run`

| 选项 | 默认 | 说明 |
|------|------|------|
| `-i / --input` | 必填 | FASTQ 文件或目录 |
| `-o / --outdir` | `./results` | 输出目录 |
| `-m / --mode` | `mock` | `mock` \| `local` \| `conda` \| `docker` |
| `-q / --query` | 通用分析句 | 自然语言问题（影响剧本、生物验证、文献） |
| `--metadata` | 无 | `sample_id,group` 的 TSV/CSV |
| `-c / --config` | `config/default.yaml` | YAML 覆盖 |
| `-y / --yes` | false | 强制自动确认 HITL |

```bash
# 演示
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "IBD gut microbiome biomarker discovery"

# 真实数据
meta-agent run -i /data/fastq -o /data/out --mode local \
  -c config/default.yaml --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

### `meta-agent serve`

```bash
meta-agent serve --host 127.0.0.1 --port 8000
# GET  /health
# POST /analyze
```

### `meta-agent version`

打印当前版本。

## 配置要点（`config/default.yaml`）

| 段 | 作用 |
|------|------|
| `routing.*` | gLM / 双路 / ε-greedy |
| `paths.*` | 数据库、`glm_weights`、`glm_inference_cmd` |
| `pipeline.*` | 是否组装、分类工具列表 |
| `validation.contract_hard_fail` | 契约 ERROR 时是否中止 swarm |
| `literature.*` | PubMed / Europe PMC / OpenAlex / Semantic Scholar |
| `statistics.lefse_like` / `ancom_like` | 近似差异方法开关 |
| `rag.mode` | `keyword` \| `semantic`（TF-IDF） |
| `pi.max_replans` | PI Agent 最多复盘次数 |
| `report.manuscript_template` | Nature / Cell / ISME / Microbiome / Gut Microbes |
| `hitl.auto_confirm` | 非交互默认；生产建议 `false` |
| `project.*` | Memory 中的 host/platform 等 |

环境变量：`.env` 中 `OPENAI_API_KEY`、`OPENAI_BASE_URL`（DeepSeek / vLLM / Ollama）。

## 元数据

```tsv
sample_id	group
S1	IBD
S2	Control
```

无分组时，mock/`demo_mode` 可能使用合成对照——Methods 须说明。

## 推荐流程

1. `mock` + `pytest -q` 冒烟  
2. 小规模 `local`/`conda`，`enable_assembly: false`  
3. 需要 MAGs 时打开组装并确认内存  
4. 长读长：读长 ≥5000 bp 走 gLM 路由；配置权重后再解读  
5. 投稿：提交 `methods.md`、`reproduce.sh`、`reproducibility/`、`evidence/`、`workflow/dag.json`

## 外部工作流

```bash
# Snakemake（委托 meta-agent）
snakemake -j 4 --configfile config/default.yaml \
  --config input_dir=tests/fixtures/fastq outdir=results mode=mock

# Nextflow
nextflow run workflow/nextflow/main.nf --input tests/fixtures/fastq --outdir results --mode mock
```

## 排障

| 现象 | 处理 |
|------|------|
| HITL 卡住 | `--yes` 或 `hitl.auto_confirm: true` |
| 契约硬失败 | 检查 FASTQ/契约；或设 `contract_hard_fail: false` |
| 分类率低 | Critic 会建议 MetaPhlAn/gLM；检查 DB 路径 |
| OOM / 137 | Self-heal 降参数或降级 assembler |
| 文献为空 | mock 下用 curated；在线需网络且 `literature.online: true` |
| gLM 未生效 | 配置 `glm_weights` 与可选 `glm_inference_cmd` |

架构细节见 [ARCHITECTURE.md](ARCHITECTURE.md)。
