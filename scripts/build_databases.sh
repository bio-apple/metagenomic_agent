#!/usr/bin/env bash
# Build / download skeleton for metagenomic_agent reference databases.
# Usage:
#   export DB_ROOT=/ref/databases   # or $(pwd)/database
#   export THREADS=32
#   bash scripts/build_databases.sh --layout
#   bash scripts/build_databases.sh --host /path/to/hg38.fa
#   bash scripts/build_databases.sh --kraken-download   # needs wget URL env
#   bash scripts/build_databases.sh --metaphlan
#   bash scripts/build_databases.sh --check
#
# This script does NOT auto-fetch multi-GB blobs without explicit flags.
# Follow database/README.md for official URLs and tool versions.

set -euo pipefail

DB_ROOT="${DB_ROOT:-$(pwd)/database}"
THREADS="${THREADS:-16}"

usage() {
  sed -n '2,14p' "$0" | sed 's/^# //'
  exit "${1:-0}"
}

make_layout() {
  mkdir -p \
    "$DB_ROOT"/{host,kraken_db,metaphlan_db,gtdb,eggnog,diamond,humann} \
    "$DB_ROOT"/arg/{card,deeparg} \
    "$DB_ROOT"/virulence/vfdb \
    "$DB_ROOT"/{taxonomy,function,pathway,microbiome,literature}
  cat >"$DB_ROOT/PATHS.example.yaml" <<EOF
# Paste into config/site.yaml under paths:
paths:
  host_index: "${DB_ROOT}/host/hg38"
  kraken2_db: "${DB_ROOT}/kraken_db"
  metaphlan_db: "${DB_ROOT}/metaphlan_db"
  gtdb: "${DB_ROOT}/gtdb"
  eggnog: "${DB_ROOT}/eggnog"
  diamond_db: "${DB_ROOT}/diamond/uniref90.dmnd"
EOF
  echo "Layout ready under $DB_ROOT"
  echo "Example paths → $DB_ROOT/PATHS.example.yaml"
}

build_host() {
  local fa="${1:?fasta required}"
  mkdir -p "$DB_ROOT/host"
  local prefix="$DB_ROOT/host/hg38"
  if command -v bowtie2-build >/dev/null 2>&1; then
    bowtie2-build --threads "$THREADS" "$fa" "$prefix"
  else
    echo "bowtie2-build not found; use Apptainer:"
    echo "  apptainer exec docker://quay.io/biocontainers/bowtie2:2.5.3--py39hd2f008b_0 \\"
    echo "    bowtie2-build --threads $THREADS $fa $prefix"
    exit 1
  fi
  echo "host_index prefix: $prefix"
}

# Optional: KRAKEN_TARBALL_URL=https://... bash scripts/build_databases.sh --kraken-download
kraken_download() {
  local url="${KRAKEN_TARBALL_URL:?set KRAKEN_TARBALL_URL to official k2_*.tar.gz}"
  mkdir -p "$DB_ROOT/kraken_db"
  local tmp
  tmp="$(mktemp -d)"
  echo "Downloading $url ..."
  wget -O "$tmp/k2.tar.gz" "$url"
  tar -xzf "$tmp/k2.tar.gz" -C "$DB_ROOT/kraken_db" --strip-components=0
  rm -rf "$tmp"
  test -f "$DB_ROOT/kraken_db/hash.k2d" || {
    echo "ERROR: hash.k2d missing — check tarball layout"
    exit 1
  }
  echo "Kraken2 DB OK: $DB_ROOT/kraken_db"
}

metaphlan_install() {
  mkdir -p "$DB_ROOT/metaphlan_db"
  if command -v metaphlan >/dev/null 2>&1; then
    metaphlan --install --bowtie2db "$DB_ROOT/metaphlan_db"
  else
    echo "metaphlan not on PATH. Example:"
    echo "  apptainer exec docker://quay.io/biocontainers/metaphlan:4.1.0--pyhca03a8a_0 \\"
    echo "    metaphlan --install --bowtie2db $DB_ROOT/metaphlan_db"
    exit 1
  fi
}

check_dbs() {
  echo "DB_ROOT=$DB_ROOT"
  for f in \
    "$DB_ROOT/host/hg38.1.bt2" \
    "$DB_ROOT/host/hg38.1.bt2l" \
    "$DB_ROOT/kraken_db/hash.k2d" \
    "$DB_ROOT/kraken_db/taxo.k2d"
  do
    if [[ -e "$f" ]]; then echo "OK  $f"; else echo "MISS $f"; fi
  done
  [[ -d "$DB_ROOT/metaphlan_db" ]] && echo "DIR $DB_ROOT/metaphlan_db ($(find "$DB_ROOT/metaphlan_db" -type f 2>/dev/null | wc -l | tr -d ' ') files)"
  [[ -d "$DB_ROOT/gtdb" ]] && echo "DIR $DB_ROOT/gtdb"
  echo "See database/README.md for GTDB / eggNOG / DIAMOND / CARD steps."
}

case "${1:-}" in
  -h|--help) usage 0 ;;
  --layout) make_layout ;;
  --host) build_host "${2:?fasta path}" ;;
  --kraken-download) kraken_download ;;
  --metaphlan) metaphlan_install ;;
  --check) check_dbs ;;
  *) usage 1 ;;
esac
