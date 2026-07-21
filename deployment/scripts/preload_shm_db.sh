#!/usr/bin/env bash
# Preload large reference DBs into /dev/shm for Linux production speedup.
# Usage: bash deployment/scripts/preload_shm_db.sh /data/kraken2_db /dev/shm/kraken2_db
set -euo pipefail
SRC="${1:?source db path}"
DST="${2:-/dev/shm/$(basename "$SRC")}"
mkdir -p "$DST"
echo "[preload] $SRC -> $DST"
rsync -a --info=progress2 "$SRC"/ "$DST"/
echo "[preload] done: $DST"
