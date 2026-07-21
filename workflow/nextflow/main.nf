#!/usr/bin/env nextflow
// Params-driven handoff: Agent writes params.yaml/json; this workflow schedules compute.
// Do not paste LLM-generated ad-hoc shell pipelines here.

params.input = 'tests/fixtures/fastq'
params.outdir = 'results'
params.mode = 'mock'
params.threads = 8
params.memory_gb = 32
params.query = 'Analyze shotgun metagenomic samples and identify microbial biomarkers.'
params.params_file = ''

process AGENT_PIPELINE {
    cpus params.threads
    memory "${params.memory_gb} GB"
    publishDir "${params.outdir}", mode: 'copy'

    output:
    path 'final_report.html'
    path 'taxonomy_profile.tsv'
    path 'workflow', optional: true
    path 'evidence', optional: true
    path 'report', optional: true

    script:
    def paramsNote = params.params_file ? "-- note: agent params at ${params.params_file}" : ''
    """
    # Engine owns env / resume; Agent owned params are already validated (YAML/JSON).
    # ${paramsNote}
    meta-agent run --input ${params.input} --outdir . --mode ${params.mode} \
      --query "${params.query}" --yes
    """
}

workflow {
    AGENT_PIPELINE()
}
