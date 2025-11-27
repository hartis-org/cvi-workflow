cwlVersion: v1.2

$namespaces:
  s: https://schema.org/

$schemas:
  - http://schema.org/version/latest/schemaorg-current-http.rdf

$graph:
  - class: Workflow
    id: cvi-workflow
    label: CVI Workflow (Dockerized)
    doc: |
      This workflow computes the Coastal Vulnerability Index (CVI) for Mediterranean coastal areas.
      It processes coastline data, generates transects, computes various coastal parameters
      (landcover, slope, erosion, elevation), and calculates the final CVI values.
    
    requirements:
      StepInputExpressionRequirement: {}
      InlineJavascriptRequirement: {}
    
    s:author:
      - class: s:Person
        s:name: HARTIS Organization
        s:url: https://github.com/hartis-org
    
    s:codeRepository: https://github.com/hartis-org/cvi-workflow
    s:dateCreated: "2024-01-01"
    s:license: https://opensource.org/licenses/MIT
    s:version: "1.0.0"
    s:keywords: CVI, coastal vulnerability, Mediterranean, earth observation
    
    inputs:
      config_stac_item_url:
        type: string
        label: Configuration STAC item URL
        doc: URL of the STAC item containing the configuration JSON file
        default: "https://eocatalog.p2.csgroup.space/collections/cvi-workflow-resources/items/cvi-scoring-configuration"
      
      aois_stac_item_url:
        type: string
        label: AOIs STAC item URL
        doc: URL of the STAC item containing the Mediterranean AOIs CSV file
        default: "https://eocatalog.p2.csgroup.space/collections/cvi-workflow-resources/items/mediterranean-coastal-aois"
      
      tokens_stac_item_url:
        type: string
        label: Tokens STAC item URL
        doc: URL of the STAC item containing the authentication tokens file
        default: "https://eocatalog.p2.csgroup.space/collections/cvi-workflow-resources/items/cvi-authentication-template"
    
    outputs:
      validated_config:
        type: File
        label: Validated configuration
        doc: Validated configuration JSON file
        outputSource: setup_env/config_validated
      
      coastline_gpkg:
        type: File
        label: Coastline GeoPackage
        doc: Extracted coastline geometry in GeoPackage format
        outputSource: extract_coastline/coastline_gpkg
      
      transects_geojson:
        type: File
        label: Generated transects
        doc: Perpendicular transects generated along the coastline
        outputSource: generate_transects/transects_geojson
      
      transects_landcover:
        type: File
        label: Transects with landcover data
        doc: Transects enriched with landcover information
        outputSource: compute_landcover/result
      
      transects_slope:
        type: File
        label: Transects with slope data
        doc: Transects enriched with slope information
        outputSource: compute_slope/result
      
      transects_erosion:
        type: File
        label: Transects with erosion data
        doc: Transects enriched with erosion information
        outputSource: compute_erosion/result
      
      transects_elevation:
        type: File
        label: Transects with elevation data
        doc: Transects enriched with elevation information
        outputSource: compute_elevation/result
      
      cvi_geojson:
        type: File
        label: CVI results
        doc: Final Coastal Vulnerability Index values for all transects
        outputSource: compute_cvi/out_geojson
    
    steps:
      node_eodag_download_config:
        label: Download configuration [EODAG]
        doc: Download the configuration JSON file from STAC item
        run: '#eodag_search'
        in:
          stac_item_url: config_stac_item_url
        out: [data_output_dir]
      
      node_eodag_download_aois:
        label: Download AOIs [EODAG]
        doc: Download the Mediterranean AOIs CSV from STAC item
        run: '#eodag_search'
        in:
          stac_item_url: aois_stac_item_url
        out: [data_output_dir]
      
      node_eodag_download_tokens:
        label: Download tokens [EODAG]
        doc: Download the authentication tokens file from STAC item
        run: '#eodag_search'
        in:
          stac_item_url: tokens_stac_item_url
        out: [data_output_dir]
      
      setup_env:
        label: Setup Environment
        run: "#setup-env-tool"
        in:
          config_json:
            source: node_eodag_download_config/data_output_dir
            valueFrom: $(self.listing.filter(function(f) { return f.basename.match(/.*\.json$/i); })[0])
          output_dir: { default: "output_data" }
        out: [config_validated]
      
      extract_coastline:
        label: Extract Coastline
        run: "#extract-coastline-tool"
        in:
          med_aois_csv:
            source: node_eodag_download_aois/data_output_dir
            valueFrom: $(self.listing.filter(function(f) { return f.basename.match(/.*\.csv$/i); })[0])
          output_dir: { default: "output_data" }
        out: [coastline_gpkg]
      
      generate_transects:
        label: Generate Transects
        run: "#generate-transects-tool"
        in:
          coastline_gpkg: extract_coastline/coastline_gpkg
          output_dir: { default: "output_data" }
        out: [transects_geojson]
      
      compute_landcover:
        label: Compute Landcover
        run: "#compute-parameter-tool"
        in:
          script: { default: { class: File, location: steps/compute_landcover.py } }
          transects_geojson: generate_transects/transects_geojson
          tokens_env:
            source: node_eodag_download_tokens/data_output_dir
            valueFrom: $(self.listing.filter(function(f) { return f.basename.match(/.*\.env$/i); })[0])
          config_json: setup_env/config_validated
          output_dir: { default: "output_data" }
        out: [result]
      
      compute_slope:
        label: Compute Slope
        run: "#compute-parameter-tool"
        in:
          script: { default: { class: File, location: steps/compute_slope.py } }
          transects_geojson: generate_transects/transects_geojson
          tokens_env:
            source: node_eodag_download_tokens/data_output_dir
            valueFrom: $(self.listing.filter(function(f) { return f.basename.match(/.*\.env$/i); })[0])
          config_json: setup_env/config_validated
          output_dir: { default: "output_data" }
        out: [result]
      
      compute_erosion:
        label: Compute Erosion
        run: "#compute-parameter-tool"
        in:
          script: { default: { class: File, location: steps/compute_erosion.py } }
          transects_geojson: generate_transects/transects_geojson
          tokens_env:
            source: node_eodag_download_tokens/data_output_dir
            valueFrom: $(self.listing.filter(function(f) { return f.basename.match(/.*\.env$/i); })[0])
          config_json: setup_env/config_validated
          output_dir: { default: "output_data" }
        out: [result]
      
      compute_elevation:
        label: Compute Elevation
        run: "#compute-parameter-tool"
        in:
          script: { default: { class: File, location: steps/compute_elevation.py } }
          transects_geojson: generate_transects/transects_geojson
          tokens_env:
            source: node_eodag_download_tokens/data_output_dir
            valueFrom: $(self.listing.filter(function(f) { return f.basename.match(/.*\.env$/i); })[0])
          config_json: setup_env/config_validated
          output_dir: { default: "output_data" }
        out: [result]
      
      compute_cvi:
        label: Compute CVI Index
        run: "#compute-cvi-tool"
        in:
          transects_landcover: compute_landcover/result
          transects_slope: compute_slope/result
          transects_erosion: compute_erosion/result
          transects_elevation: compute_elevation/result
          config_json: setup_env/config_validated
          output_dir: { default: "output_data" }
        out: [out_geojson]
  
  # CommandLineTool definitions
  - class: CommandLineTool
    id: setup-env-tool
    label: Setup Environment
    doc: Validates configuration and initializes the working environment
    
    baseCommand: [python3, setup_env.py]
    
    hints:
      DockerRequirement: &docker_image
        dockerPull: ghcr.io/hartis-org/cvi-workflow:latest
    
    requirements:
      InlineJavascriptRequirement: {}
      InitialWorkDirRequirement:
        listing:
          - $(inputs.config_json)
          - { entry: $(inputs.script), entryname: setup_env.py }
          - { entry: "$({class: 'Directory', listing: []})", entryname: $(inputs.output_dir), writable: true }
    
    inputs:
      script:
        type: File
        default: { class: File, location: steps/setup_env.py }
        doc: Python script for environment setup
      
      config_json:
        type: File
        inputBinding:
          position: 1
        doc: Configuration JSON file
      
      output_dir:
        type: string
        inputBinding:
          position: 2
        doc: Output directory path
    
    outputs:
      config_validated:
        type: File
        outputBinding:
          glob: "$(inputs.output_dir)/config_validated.json"
        doc: Validated configuration file
  
  - class: CommandLineTool
    id: extract-coastline-tool
    label: Extract Coastline
    doc: Extracts coastline geometry from Mediterranean AOIs
    
    baseCommand: [python3, extract_coastline.py]
    
    hints:
      DockerRequirement: *docker_image
    
    requirements:
      InlineJavascriptRequirement: {}
      InitialWorkDirRequirement:
        listing:
          - { entry: $(inputs.script), entryname: extract_coastline.py }
          - $(inputs.med_aois_csv)
          - { entry: "$({class: 'Directory', listing: []})", entryname: $(inputs.output_dir), writable: true }
    
    inputs:
      script:
        type: File
        default: { class: File, location: steps/extract_coastline.py }
        doc: Python script for coastline extraction
      
      med_aois_csv:
        type: File
        inputBinding:
          position: 1
        doc: Mediterranean areas of interest CSV
      
      output_dir:
        type: string
        inputBinding:
          position: 2
        doc: Output directory path
    
    outputs:
      coastline_gpkg:
        type: File
        outputBinding:
          glob: "$(inputs.output_dir)/coastline.gpkg"
        doc: Extracted coastline GeoPackage
  
  - class: CommandLineTool
    id: generate-transects-tool
    label: Generate Transects
    doc: Generates perpendicular transects along the coastline
    
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
      script:
        type: File
        default: { class: File, location: steps/generate_transects.py }
        doc: Python script for transect generation
      
      coastline_gpkg:
        type: File
        inputBinding:
          position: 1
        doc: Coastline GeoPackage
      
      output_dir:
        type: string
        inputBinding:
          position: 2
        doc: Output directory path
    
    outputs:
      transects_geojson:
        type: File
        outputBinding:
          glob: "$(inputs.output_dir)/transects.geojson"
        doc: Generated transects GeoJSON
  
  - class: CommandLineTool
    id: compute-parameter-tool
    label: Compute Parameter
    doc: Computes a CVI parameter (landcover, slope, erosion, or elevation) for transects
    
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
      script:
        type: File
        inputBinding:
          position: 0
        doc: Python script for parameter computation
      
      transects_geojson:
        type: File
        inputBinding:
          position: 1
        doc: Transects GeoJSON file
      
      tokens_env:
        type: File
        inputBinding:
          position: 2
        doc: Authentication tokens file
      
      config_json:
        type: File
        inputBinding:
          position: 3
        doc: Configuration JSON file
      
      output_dir:
        type: string
        inputBinding:
          position: 4
        doc: Output directory path
    
    outputs:
      result:
        type: File
        outputBinding:
          glob: "$(inputs.output_dir)/*.geojson"
        doc: Transects enriched with parameter data
  
  - class: CommandLineTool
    id: compute-cvi-tool
    label: Compute CVI
    doc: Computes final Coastal Vulnerability Index from all parameters
    
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
      script:
        type: File
        default: { class: File, location: steps/compute_cvi.py }
        doc: Python script for CVI computation
      
      transects_landcover:
        type: File
        inputBinding:
          position: 1
        doc: Transects with landcover data
      
      transects_slope:
        type: File
        inputBinding:
          position: 2
        doc: Transects with slope data
      
      transects_erosion:
        type: File
        inputBinding:
          position: 3
        doc: Transects with erosion data
      
      transects_elevation:
        type: File
        inputBinding:
          position: 4
        doc: Transects with elevation data
      
      config_json:
        type: File
        inputBinding:
          position: 5
        doc: Configuration JSON file
      
      output_dir:
        type: string
        inputBinding:
          position: 6
        doc: Output directory path
    
    outputs:
      out_geojson:
        type: File
        outputBinding:
          glob: "$(inputs.output_dir)/transects_with_cvi_equal.geojson"
        doc: Final CVI results GeoJSON

  - class: CommandLineTool
    id: eodag_search
    label: Download input data
    doc: Downloads STAC item assets using EODAG
    
    s:softwareVersion: latest
    
    hints:
      DockerRequirement:
        dockerPull: |-
          643vlk6z.gra7.container-registry.ovh.net/space_applications/eodag:3.6.0
    
    requirements:
      InlineJavascriptRequirement: {}
      NetworkAccess:
        networkAccess: true
    
    baseCommand: [eodag, download]
    
    arguments:
      - prefix: "--output-dir"
        valueFrom: $(runtime.outdir)
    
    inputs:
      stac_item_url:
        type: string
        inputBinding:
          prefix: "--stac-item"
        doc: URL of the STAC item to download
    
    outputs:
      data_output_dir:
        type: Directory
        outputBinding:
          glob: $(runtime.outdir)/*
        doc: Directory containing downloaded STAC item assets
