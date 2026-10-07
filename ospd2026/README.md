# OSPD-2026 D100 evidence

This directory contains the HARTIS contribution to the OSPD-2026 D100
Workflow Profiler work. The parent repository remains the executable CVI
workflow; this directory adds the provenance, Building Block and register
evidence that profiles that workflow.

## Contents

- `provenance/` contains a focused coastline-to-transects chain and the
  normalized full-workflow design/runtime example.
- `building-block/prov-processing-step/` contains the current working candidate
  for a single geospatial processing-step provenance profile.
- `register/geoprocessing-activities.jsonld` contains provisional HARTIS
  activity definitions derived from the AI-DGGS FII evidence workflow and the
  `PRV004` demonstrator record.
- `report/d001-hartis-contribution.md` contains the report-ready HARTIS
  contribution for D001.
- `validation/` contains the workflow artifact manifest used to identify the
  evidence files and their checksums.
- `../docs/ospd2026-github-cwl-run.md` describes the manual Docker/CWLProv
  execution workflow.

## Relationship to the workflow

The executable workflow is defined by `cvi_workflow.cwl`, its scripts,
configuration and Docker image in the parent directory. The OSPD material does
not replace those files. It describes the processing activities, their inputs
and outputs, and the evidence needed to review the provenance profile.

The process-type identifiers in the register file are provisional. They are
not presented as official Register terms until the OSPD Register process is
confirmed.

## Reproduction

Run the parent CVI workflow using the instructions in the repository root.
The artifact manifest records the source files and checksums used for the
current evidence package. The structural validation workflow checks the
machine-readable examples. A full CVI execution remains dependent on the
external data services and credentials required by the workflow.

The full execution is available as a manual GitHub Actions workflow. It runs
the CWL workflow with Docker and uploads the resulting CWLProv package; see
`docs/ospd2026-github-cwl-run.md` for the required repository secrets and run
procedure.

## Status

This is a working D100 contribution package and report evidence set. It is
suitable for review and iteration; it is not yet a final OGC Building Block
submission.
