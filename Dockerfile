# Metagenomic Research Agent — orchestration layer (venv tools via Apptainer/Docker at runtime)
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    META_AGENT_HOME=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
# Reference DBs are NOT copied — too large; bind-mount host path at runtime (/ref).
COPY workflow ./workflow
COPY tests ./tests
COPY examples ./examples
COPY scripts ./scripts

RUN pip install -U pip setuptools wheel \
 && pip install -e ".[dev]"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Default: API server. Override for CLI:
#   docker run ... meta-agent run -i /data -o /results --mode mock --yes
ENTRYPOINT ["meta-agent"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
