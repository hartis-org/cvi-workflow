# HARTIS CVI Processing Step Provenance

This is the HARTIS implementation draft for OSPD-2026 D100. It follows the structure introduced in Aganitha's `prov-processing-step` PR to `ogcincubator/bblocks-openscience`, while testing it against the HARTIS Coastal Vulnerability Index workflow.

The first HARTIS test case is the CVI transect-generation step:

- input: `output_data/coastline.gpkg`
- output: `output_data/transects.geojson`
- source tool: `steps/generate_transects.py`
- workflow: `cvi_workflow.cwl`
- Docker image: `ghcr.io/hartis-org/cvi-workflow:latest`

This draft intentionally models a single processing activity rather than the full workflow run. That makes it easier to compare with the emerging OSPD-2026 profile-plus-register pattern:

- the profile provides the provenance structure;
- `processType` links the step to a controlled registered process type;
- inputs and outputs are referenced as entities;
- `qualifiedUsage` records the role each input played;
- `parameters` captures values needed to compare or reproduce the step.

The `processType` URI used here is provisional. It should be replaced once the OSPD-2026 process-type register and URI pattern are available.
