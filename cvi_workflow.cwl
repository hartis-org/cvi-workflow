cwlVersion: v1.2
class: Workflow
label: CVI Workflow (Dockerized)

inputs:
  config_json: File
  med_aois_csv: File
  tokens_env: File
  output_dir:
    type: string
    default: "output_data"

outputs:
  validated_config:    { type: File, outputSource: setup_env/config_validated }
  coastline_gpkg:      { type: File, outputSource: extract_coastline/coastline_gpkg }
  transects_geojson:   { type: File, outputSource: generate_transects/transects_geojson }
  transects_landcover: { type: File, outputSource: compute_landcover/result }
  transects_slope:     { type: File, outputSource: compute_slope/result }
  transects_erosion:   { type: File, outputSource: compute_erosion/result }
  transects_elevation: { type: File, outputSource: compute_elevation/result }
  cvi_geojson:         { type: File, outputSource: compute_cvi/out_geojson }

steps:
  # ---------------------------------------------------------
  # Step 1: Setup (DEFINES THE DOCKER IMAGE HERE)
  # ---------------------------------------------------------
  setup_env:
    run:
      class: CommandLineTool
      baseCommand: [python3, setup_env.py]
      hints:
        # WE DEFINE THE IMAGE ONCE HERE WITH '&docker_image'
        DockerRequirement: &docker_image
          # Format: ghcr.io/<org_name>/<repo_name>:latest
          dockerPull: ghcr.io/hartis-org/cvi-workflow:latest
      requirements:
        InlineJavascriptRequirement: {}
        InitialWorkDirRequirement:
          listing:
            - $(inputs.config_json)
            - { entry: $(inputs.script), entryname: setup_env.py }
            - { entry: "$({class: 'Directory', listing: []})", entryname: $(inputs.output_dir), writable: true }
      inputs:
        script:      { type: File, default: { class: File, location: steps/setup_env.py } }
        config_json: { type: File, inputBinding: { position: 1 } }
        output_dir:  { type: string, inputBinding: { position: 2 } }
      outputs:
        config_validated: { type: File, outputBinding: { glob: "$(inputs.output_dir)/config_validated.json" } }
    in:
      config_json: config_json
      output_dir: output_dir
    out: [config_validated]

  # ---------------------------------------------------------
  # Step 2: Coastline (USES THE DEFINED IMAGE)
  # ---------------------------------------------------------
  extract_coastline:
    run:
      class: CommandLineTool
      baseCommand: [python3, extract_coastline.py]
      hints:
        # REUSE THE IMAGE DEFINITION
        DockerRequirement: *docker_image
      requirements:
        InlineJavascriptRequirement: {}
        InitialWorkDirRequirement:
          listing:
            - { entry: $(inputs.script), entryname: extract_coastline.py }
            - $(inputs.med_aois_csv)
            - { entry: "$({class: 'Directory', listing: []})", entryname: $(inputs.output_dir), writable: true }
      inputs:
        script:       { type: File, default: { class: File, location: steps/extract_coastline.py } }
        med_aois_csv: { type: File, inputBinding: { position: 1 } }
        output_dir:   { type: string, inputBinding: { position: 2 } }
      outputs:
        coastline_gpkg: { type: File, outputBinding: { glob: "$(inputs.output_dir)/coastline.gpkg" } }
    in:
      med_aois_csv: med_aois_csv
      output_dir: output_dir
    out: [coastline_gpkg]

  # ---------------------------------------------------------
  # Step 3: Transects
  # ---------------------------------------------------------
  generate_transects:
    run:
      class: CommandLineTool
      baseCommand: [python3, generate_transects.py]
      hints:
        DockerRequirement: *docker_image
      requirements:
        InlineJavascriptRequirement: {}
        InitialWorkDirRequirement:
          listing:
            - $(inputs.coastline_gpkg)
            - { entry: $(inputs.script), entryname: generate_transects.py }
            - { entry: "$({class: 'Directory', listing: []})", entryname: $(inputs.output_dir), writable: true }
      inputs:
        script:         { type: File, default: { class: File, location: steps/generate_transects.py } }
        coastline_gpkg: { type: File, inputBinding: { position: 1 } }
        output_dir:     { type: string, inputBinding: { position: 2 } }
      outputs:
        transects_geojson: { type: File, outputBinding: { glob: "$(inputs.output_dir)/transects.geojson" } }
    in:
      coastline_gpkg: extract_coastline/coastline_gpkg
      output_dir: output_dir
    out: [transects_geojson]

  # ---------------------------------------------------------
  # Step 4: Landcover (DEFINES THE TOOL TEMPLATE)
  # ---------------------------------------------------------
  compute_landcover:
    run: &compute_tool
      class: CommandLineTool
      baseCommand: [python3]
      hints:
        DockerRequirement: *docker_image
      requirements:
        InlineJavascriptRequirement: {}
        InitialWorkDirRequirement:
          listing:
            - entry: $(inputs.transects_geojson)
            - entry: $(inputs.tokens_env)
            - entry: $(inputs.config_json)
            - entry: $(inputs.script)
            - entry: "$({class: 'Directory', listing: []})"
              entryname: $(inputs.output_dir)
              writable: true
      inputs:
        script:            { type: File, inputBinding: { position: 0 } }
        transects_geojson: { type: File, inputBinding: { position: 1 } }
        tokens_env:        { type: File, inputBinding: { position: 2 } }
        config_json:       { type: File, inputBinding: { position: 3 } }
        output_dir:        { type: string, inputBinding: { position: 4 } }
      outputs:
        result:
          type: File
          outputBinding: { glob: "$(inputs.output_dir)/*.geojson" }
    in:
      script: { default: { class: File, location: steps/compute_landcover.py } }
      transects_geojson: generate_transects/transects_geojson
      tokens_env: tokens_env
      config_json: setup_env/config_validated
      output_dir: output_dir
    out: [result]

  # ---------------------------------------------------------
  # Step 5: Slope
  # ---------------------------------------------------------
  compute_slope:
    run: *compute_tool
    in:
      script: { default: { class: File, location: steps/compute_slope.py } }
      transects_geojson: generate_transects/transects_geojson
      tokens_env: tokens_env
      config_json: setup_env/config_validated
      output_dir: output_dir
    out: [result]

  # ---------------------------------------------------------
  # Step 6: Erosion
  # ---------------------------------------------------------
  compute_erosion:
    run: *compute_tool
    in:
      script: { default: { class: File, location: steps/compute_erosion.py } }
      transects_geojson: generate_transects/transects_geojson
      tokens_env: tokens_env
      config_json: setup_env/config_validated
      output_dir: output_dir
    out: [result]

  # ---------------------------------------------------------
  # Step 7: Elevation
  # ---------------------------------------------------------
  compute_elevation:
    run: *compute_tool
    in:
      script: { default: { class: File, location: steps/compute_elevation.py } }
      transects_geojson: generate_transects/transects_geojson
      tokens_env: tokens_env
      config_json: setup_env/config_validated
      output_dir: output_dir
    out: [result]

  # ---------------------------------------------------------
  # Step 8: Final CVI
  # ---------------------------------------------------------
  compute_cvi:
    run:
      class: CommandLineTool
      baseCommand: [python3, compute_cvi.py]
      hints:
        DockerRequirement: *docker_image
      requirements:
        InlineJavascriptRequirement: {}
        InitialWorkDirRequirement:
          listing:
            - $(inputs.transects_landcover)
            - $(inputs.transects_slope)
            - $(inputs.transects_erosion)
            - $(inputs.transects_elevation)
            - $(inputs.config_json)
            - { entry: $(inputs.script), entryname: compute_cvi.py }
            - { entry: "$({class: 'Directory', listing: []})", entryname: $(inputs.output_dir), writable: true }
      inputs:
        script:              { type: File, default: { class: File, location: steps/compute_cvi.py } }
        transects_landcover: { type: File, inputBinding: { position: 1 } }
        transects_slope:     { type: File, inputBinding: { position: 2 } }
        transects_erosion:   { type: File, inputBinding: { position: 3 } }
        transects_elevation: { type: File, inputBinding: { position: 4 } }
        config_json:         { type: File, inputBinding: { position: 5 } }
        output_dir:          { type: string, inputBinding: { position: 6 } }
      outputs:
        out_geojson: { type: File, outputBinding: { glob: "$(inputs.output_dir)/transects_with_cvi_equal.geojson" } }
    in:
      transects_landcover: compute_landcover/result
      transects_slope: compute_slope/result
      transects_erosion: compute_erosion/result
      transects_elevation: compute_elevation/result
      config_json: setup_env/config_validated
      output_dir: output_dir
    out: [out_geojson]