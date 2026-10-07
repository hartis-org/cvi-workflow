# OSPD-2026 GitHub CVI run

The `ospd2026-cwl-run.yml` workflow runs the CVI workflow on a GitHub-hosted
runner. Each CWL processing step uses the Docker image built from this
repository. The workflow also requests a CWLProv provenance package from
`cwltool` and uploads the outputs and provenance as one GitHub Actions artifact.
The run uses `cwltool --enable-net` because the coastline extraction step calls
the public Nominatim and Overpass services.

## Required repository secrets

Configure these secrets in the GitHub repository before starting the manual
workflow:

- `CDSE_AWS_ACCESS_KEY_ID`
- `CDSE_AWS_SECRET_ACCESS_KEY`
- `CDSE_AWS_ENDPOINT_URL`
- `CDSE_AWS_DEFAULT_REGION`

The values are written to a temporary `config/tokens.env` file only during the
run. The cleanup step removes that file whether the run succeeds or fails.

## Starting a run

Open **Actions**, select **Run CVI workflow with Docker and CWLProv**, choose
**Run workflow**, and inspect the uploaded artifact named with the GitHub run
ID. It contains the workflow outputs under `output/` and the CWLProv package
under `cwlprov/`.

The existing `docker-build.yml` workflow remains responsible for publishing the
container image on pushes to `main`. This workflow is deliberately manual
because it accesses external data services and consumes project credentials.
