#!/usr/bin/env nextflow
// Staged handoff documenting QC/Tax → Evidence/Report. Compute via meta-agent.

params.input = 'tests/fixtures/fastq'
params.outdir = 'results'
params.mode = 'mock'
params.threads = 8
params.query = 'Analyze shotgun metagenomic samples and identify microbial biomarkers.'

process AGENT_PIPELINE {
    cpus params.threads
    publishDir "${params.outdir}", mode: 'copy'

    output:
    path 'final_report.html'
    path 'taxonomy_profile.tsv'
    path 'workflow', optional: true
    path 'evidence', optional: true
    path 'report', optional: true

    script:
    """
    meta-agent run --input ${params.input} --outdir . --mode ${params.mode} \
      --query "${params.query}" --yes
    """
}

workflow {
    AGENT_PIPELINE()
}
