#!/usr/bin/env bash
set -euo pipefail
meta-agent run --input /Users/yfan/Desktop/bio-apple/metagenomic_agent/tests/fixtures/fastq --outdir /Users/yfan/Desktop/bio-apple/metagenomic_agent/results_mags --mode mock --yes --query "\u5206\u6790\u6211\u7684\u80a0\u9053\u5b8f\u57fa\u56e0\u7ec4 FASTQ\uff0c\u8fdb\u884c MAG \u5206\u7bb1\u4e0e IBD biomarker \u5206\u6790"
