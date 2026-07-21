#!/usr/bin/env nextflow
// Metagenomic Research Agent — Nextflow handoff skeleton
// Generated configs land in results/nextflow/agent.nf.config

params.input = 'tests/fixtures/fastq'
params.outdir = 'results'
params.mode = 'mock'
params.threads = 8

process AGENT_ORCHESTRATE {
    cpus params.threads
    publishDir "${params.outdir}", mode: 'copy'

    output:
    path 'final_report.html'

    script:
    """
    meta-agent run --input ${params.input} --outdir . --mode ${params.mode} --yes
    """
}

workflow {
    AGENT_ORCHESTRATE()
}
