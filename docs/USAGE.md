# 使用指南（USAGE）

## CLI

入口命令：`meta-agent`（见 `pyproject.toml` → `[project.scripts]`）。

### `meta-agent run`

| 选项 | 默认 | 说明 |
|------|------|------|
| `-i / --input` | 必填 | FASTQ 文件或目录 |
| `-o / --outdir` | `./results` | 输出目录 |
| `-m / --mode` | `mock` | `mock` \| `local` \| `conda` \| `docker` |
| `-q / --query` | 通用分析句 | 自然语言研究问题（影响剧本与生物验证上下文） |
| `--metadata` | 无 | 含 `sample_id,group` 的 TSV/CSV |
| `-c / --config` | `config/default.yaml` | YAML 覆盖配置 |
| `-y / --yes` | false | 强制自动确认 HITL |

示例：

```bash
# 演示
meta-agent run -i tests/fixtures/fastq -o ./results --mode mock --yes \
  -q "Healthy gut microbiome profiling"

# 真实工具（需本机安装 + 数据库路径）
meta-agent run -i /data/fastq -o /data/out --mode local \
  -c config/default.yaml \
  --metadata /data/meta.tsv \
  -q "IBD vs healthy biomarker discovery"
```

### `meta-agent serve`

```bash
meta-agent serve --host 127.0.0.1 --port 8000
```

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/analyze` | 同步跑完整流水线（API 内默认 `hitl.auto_confirm=true`） |

请求体字段：`input_path`, `outdir`, `query`, `mode`, `metadata_path`, `config_path`。

### `meta-agent version`

打印包版本（当前 `0.5.0`）。

## 配置分层

1. 内置默认：`config/default.yaml`
2. `-c` 指定文件覆盖
3. CLI `--mode` / `--yes` 运行时覆盖

### 常用段落

```yaml
routing:
  enable_glm: true      # 允许 gLM 路由
  dual_path: true       # 短读长可传统+gLM 融合（按路由逻辑）
  epsilon: 0.15         # ε-greedy 探索率

pipeline:
  enable_assembly: false
  taxonomy_tools: ["kraken2", "metaphlan"]

paths:
  kraken2_db: "database/kraken_db"
  glm_weights: ""       # 空则 gLM 走桩/mock

hitl:
  auto_confirm: true    # 交互生产环境建议 false

validation:
  min_read_retention: 0.3
  require_gut_markers: true
```

环境变量：`.env` 中可配 `OPENAI_API_KEY`、`OPENAI_BASE_URL`（兼容 DeepSeek / vLLM / Ollama）。

## 推荐工作流

1. **工程冒烟**：`mock` + `pytest -q`
2. **小规模真数据**：`local`/`conda`，`enable_assembly: false`，先跑 QC+分类+统计
3. **MAGs**：打开 `pipeline.enable_assembly`，确认内存/`linux.memory_gb` 与 CheckM 阈值
4. **长读长**：确保测序特征被识别（读长 ≥ 5000 bp 时优先 `microcafe` 路由）；配置 `glm_weights` 后再解读分类结果
5. **投稿复现**：提交 `report/methods.md`、`reproduce.sh`、`reproducibility/` 目录

## 元数据格式

```tsv
sample_id	group
S1	IBD
S2	Control
```

无分组时，统计模块在 `statistics.demo_mode` 或 mock 下可能使用合成对照矩阵——Methods 中需如实说明。

## 故障排查

| 现象 | 处理 |
|------|------|
| HITL 卡住 | 加 `--yes`，或设 `hitl.auto_confirm: true` |
| 契约失败进 HITL | 检查上游 FASTQ/质控产物是否满足 skill 输入契约 |
| 分类率过低 | Critic 会建议 MetaPhlAn / gLM；检查数据库路径 |
| OOM / exit 137 | Self-heal 会降组装参数或降级 assembler |
| 生物学 WARN | 阅读 `biological_context.json`；核对研究背景与 query 措辞 |

更多实现细节见 [ARCHITECTURE.md](ARCHITECTURE.md)。
