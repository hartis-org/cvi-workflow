# Coastal Vulnerability Index (CVI) Workflow

![Build Status](https://github.com/hartis-org/cvi-workflow/actions/workflows/docker-build.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)
![Docker](https://img.shields.io/badge/container-ghcr.io-blue)
![OGC](https://img.shields.io/badge/OGC-OSPD%20Pilot-blue)

An automated, reproducible workflow for calculating the **Coastal Vulnerability Index (CVI)**. This system generates coastal transects, fetches satellite data (DEM, Land Cover), computes physical parameters, and classifies coastal risk based on the USGS/NOAA methodology.

The workflow is implemented in **Common Workflow Language (CWL)** and runs inside a **Docker container**, ensuring it can be executed anywhere—from a local laptop to a High-Performance Computing (HPC) cluster or JupyterHub.

---

## 🏆 OGC Open Science Persistent Demonstrator (OSPD)

This workflow is developed as a contribution to the **[OGC Open Science Persistent Demonstrator (OSPD) Pilot](https://www.ogc.org/initiatives/open-science/)**.

It demonstrates a **reproducible, cloud-agnostic Earth Science workflow** by adhering to OSPD principles:
*   **Standardization:** Uses **Common Workflow Language (CWL)** to ensure the logic runs on any compliant runner (cwltool, Argo, Toil).
*   **Portability:** Uses **Docker/OCI Containers** to guarantee the exact same environment on a local laptop, JupyterHub, or HPC.
*   **Open Science:** All inputs, code, and configuration are open and versioned, allowing full verification of the scientific results.

---

## 🌍 Scientific Overview

The CVI assesses the susceptibility of a coastline to hazards like erosion and inundation. This workflow automates:

1.  **Coastline Extraction:** Identifies the coastline for specific Areas of Interest (AOI).
2.  **Transect Generation:** Creates perpendicular transects (e.g., every 500m) along the coast.
3.  **Data Retrieval & Calculation:**
    *   **Slope:** Derived from **Copernicus DEM (GLO-30)** via S3 API.
    *   **Elevation:** Derived from Copernicus DEM.
    *   **Land Cover:** Derived from ESA WorldCover/Global Land Cover.
    *   **Erosion:** Calculated based on historical shoreline trends.
4.  **Scoring & Classification:** Ranks variables (1–5) based on configurable thresholds.
5.  **Final Index:** Computes the final CVI score (`sqrt(product/n)`).


---

## 📂 Repository Structure

```text
cvi-workflow/
├── .github/workflows/   # GitHub Actions for building Docker images
├── config/
│   ├── cvi_scoring_simple.json  # Thresholds, weights, and scoring logic
│   └── tokens.env.example       # Template for API credentials
├── input_data/
│   └── med_coastal_aois.csv     # List of locations to process
├── steps/               # Python scripts for each workflow step
│   ├── extract_coastline.py
│   ├── generate_transects.py
│   ├── compute_slope.py
│   ├── compute_erosion.py
│   └── ...
├── cvi_workflow.cwl     # Main CWL Workflow definition
├── job_cvi.yaml         # Input parameters for the workflow run
├── Dockerfile           # Environment definition (GDAL, Python libs)
└── README.md            # This file
```

---

## ⚙️ Prerequisites

### 1. Credentials
You need access to the **Copernicus Dataspace Ecosystem (CDSE)** to fetch elevation data.
1.  Create a file named `config/tokens.env`.
2.  Add your S3 credentials:
    ```bash
    AWS_ACCESS_KEY_ID=<your_access_key>
    AWS_SECRET_ACCESS_KEY=<your_secret_key>
    AWS_ENDPOINT_URL=https://eodata.dataspace.copernicus.eu
    AWS_DEFAULT_REGION=eu-central-1
    ```

### 2. Tools
You need **Python 3** and **cwltool**.
```bash
pip install cwltool
```

---

## 🚀 How to Run

This workflow uses a Docker image hosted at `ghcr.io/hartis-org/cvi-workflow:latest`.

### Option A: Running on Local Machine (with Docker)
If you have Docker installed and running:
```bash
cwltool --outdir ./output_data cvi_workflow_docker.cwl job_cvi.yaml
```

### Option B: Running on JupyterHub / HPC (No Root Access)
If you are in a restricted environment (like JupyterHub) where you cannot run standard Docker, use **udocker**.

1.  **Install udocker:**
    ```bash
    pip install udocker
    udocker install
    ```

2.  **Configure Permissions:**
    *Critical Step:* On many shared servers, `/tmp` is blocked for execution (noexec). You must tell udocker to use your home directory instead.
    ```bash
    mkdir -p ~/udocker_tmp
    export PROOT_TMP_DIR=~/udocker_tmp
    ```

3.  **Login (If package is Private):**
    ```bash
    udocker login --username <github_user> --password <pat_token> ghcr.io
    ```

4.  **Run the Workflow:**
    ```bash
    cwltool \
      --user-space-docker-cmd=udocker \
      --outdir ./output_data \
      cvi_workflow_docker.cwl \
      job_cvi.yaml
    ```

---

## 📊 Outputs

All results are saved to the `output_data/` directory defined in `job_cvi.yaml`.

| File | Description |
| :--- | :--- |
| `config_validated.json` | The configuration used for the run. |
| `coastline.gpkg` | Extracted coastline geometry. |
| `transects.geojson` | Raw transects. |
| `transects_with_slope.geojson` | Transects with computed slope values and ranks. |
| `transects_with_elevation.geojson` | Transects with elevation stats. |
| `transects_with_land_cover.geojson`| Transects with land cover classes. |
| **`transects_with_cvi_equal.geojson`** | **Final Result:** Contains the calculated CVI score and traffic-light risk colors. |

---

## 🛠️ Development

### Updating the Docker Image
The Docker image is built automatically via **GitHub Actions** whenever you push changes to `main`.

1.  Update `requirements.txt` or `Dockerfile`.
2.  Push to GitHub.
3.  Wait for the Action to complete.
4.  The CWL will automatically pull the new `latest` tag on the next run.

### Modifying Scoring Logic
To change how risk categories are defined (e.g., changing "High Risk" slope from <2% to <3%), edit **`config/cvi_scoring_simple.json`**. The workflow reads this file dynamically—no code changes required.

---

## 🗺️ Visualization

The output GeoJSON files contain pre-calculated color codes defined in the config. You can verify the results using Python/Folium:

```python
import json
import geopandas as gpd
import folium
from folium import FeatureGroup, LayerControl
import numpy as np

# ==========================================
# 1. Load Configuration
# ==========================================
config_path = "config/cvi_scoring_simple.json"

try:
    with open(config_path, "r") as f:
        config = json.load(f)
except FileNotFoundError:
    print(f"⚠️ Config file not found at {config_path}.")
    raise

# Extract the "Master" Palette (1-5 -> Green-Red) for general use
default_palette = {
    k: v["color_hex"] 
    for k, v in config["meta"]["default_palette"].items()
}

# ==========================================
# 2. Helper: Color Lookup Logic
# ==========================================
def get_layer_style(feature, layer_type, config, default_palette):
    """
    Determines the color based on the '_score' column found in the GeoJSON
    and the definitions in the config JSON.
    """
    props = feature.get("properties", {})
    
    # Default fallback color (Gray for missing data/NaN)
    color = "#999999"
    opacity = 0.8
    
    try:
        score_val = None
        
        # --- A. LAND COVER (Unique Config Colors) ---
        if layer_type == "land_cover":
            # The file has 'land_cover_score' (1.0 to 5.0)
            val = props.get("land_cover_score")
            
            # Check if valid number (not None or NaN)
            if val is not None and not np.isnan(val):
                # Convert 1.0 -> "1"
                key = str(int(val))
                # Use specific colors defined in config["land_cover"]["classes"]
                if key in config["land_cover"]["classes"]:
                    color = config["land_cover"]["classes"][key]["color_hex"]
            else:
                # If land cover is NaN (like in your sample), make it faint gray
                opacity = 0.3

        # --- B. PHYSICAL VARIABLES (Slope, Erosion, Elevation) ---
        elif layer_type in ["slope", "erosion", "elevation"]:
            # The files have 'slope_score', 'erosion_score', etc.
            col_name = f"{layer_type}_score"
            val = props.get(col_name)
            
            if val is not None and not np.isnan(val):
                # Convert 1.0 -> "1"
                key = str(int(val))
                # Map 1-5 score to the Default Traffic Light Palette
                color = default_palette.get(key, color)

        # --- C. FINAL CVI ---
        elif layer_type == "cvi":
            # The file uses 'CVI_equal_class' (1, 2, 3, 4, 5)
            val = props.get("CVI_equal_class")
            
            if val is not None and not np.isnan(val):
                key = str(int(val))
                color = default_palette.get(key, color)

    except Exception as e:
        # Keep default gray if parsing fails
        pass

    return {
        "color": color,
        "weight": 4,
        "opacity": opacity
    }

# ==========================================
# 3. Define Layers to Load
# ==========================================
layers_info = [
    {
        "name": "1. Land Cover",
        "type": "land_cover",
        "file": "./output_data/transects_with_land_cover.geojson"
    },
    {
        "name": "2. Slope",
        "type": "slope",
        "file": "./output_data/transects_with_slope.geojson"
    },
    {
        "name": "3. Erosion",
        "type": "erosion",
        "file": "./output_data/transects_with_erosion.geojson"
    },
    {
        "name": "4. Elevation",
        "type": "elevation",
        "file": "./output_data/transects_with_elevation.geojson"
    },
    {
        "name": "5. Final CVI (Equal)",
        "type": "cvi",
        "file": "./output_data/transects_with_cvi_equal.geojson"
    }
]

# ==========================================
# 4. Initialize Map
# ==========================================
# Load CVI first to center the map
gdf_center = gpd.read_file("./output_data/transects_with_cvi_equal.geojson")
center = gdf_center.unary_union.centroid
m = folium.Map(location=[center.y, center.x], zoom_start=11, tiles="CartoDB positron")

# ==========================================
# 5. Add Layers
# ==========================================
for layer in layers_info:
    try:
        gdf = gpd.read_file(layer["file"])
        
        # Only show CVI by default
        is_visible = (layer["type"] == "cvi")
        
        fg = FeatureGroup(name=layer["name"], show=is_visible)
        
        # Dynamically get all columns for tooltip (except geometry)
        tooltip_cols = [c for c in gdf.columns if c != 'geometry']
        
        folium.GeoJson(
            gdf,
            style_function=lambda feature, ltype=layer["type"]: get_layer_style(
                feature, ltype, config, default_palette
            ),
            tooltip=folium.GeoJsonTooltip(fields=tooltip_cols, localize=True)
        ).add_to(fg)
        
        fg.add_to(m)
        print(f"✅ Added layer: {layer['name']}")
        
    except Exception as e:
        print(f"❌ Could not load {layer['file']}: {e}")

# ==========================================
# 6. Add Legend
# ==========================================
legend_items_html = ""
sorted_keys = sorted(config["meta"]["default_palette"].keys())

for key in sorted_keys:
    item = config["meta"]["default_palette"][key]
    color = item["color_hex"]
    
    label = f"Score {key}" 
    if key == "1": label += " (Low Vuln.)"
    if key == "5": label += " (High Vuln.)"
    
    legend_items_html += f"""
    <div style="margin-bottom: 4px;">
        <span style="background:{color};width:12px;height:12px;display:inline-block;border:1px solid #999;margin-right:5px;"></span>
        {label}
    </div>
    """

legend_html = f"""
<div style="
     position: fixed;
     bottom: 30px;
     left: 30px;
     width: 160px;
     z-index: 9999;
     background: white;
     padding: 10px;
     border-radius: 6px;
     border: 2px solid rgba(0,0,0,0.2);
     font-size: 13px;
     font-family: sans-serif;">
     <b>CVI Scores</b><hr style="margin: 5px 0;">
     {legend_items_html}
     <hr style="margin: 5px 0;">
     <small><i>Gray = No Data</i></small>
</div>
"""

m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m)

m
```

---

**Author:** [HARTIS Integrated Nautical Services PC](https:www.hartis.org)  
**Repository:** [github.com/hartis-org/cvi-workflow](https://github.com/hartis-org/cvi-workflow)  
**Initiative:** [OGC Open Science Persistent Demonstrator](https://www.ogc.org/initiatives/open-science/)
