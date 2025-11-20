#!/usr/bin/env python3
"""
Compute Coastal Elevation (Copernicus DEM via S3)
-------------------------------------------------
Downloads Copernicus DEM tiles from the Copernicus Dataspace S3 bucket,
clips them around transects, computes MAX elevation per transect, and
classifies according to CVI config.

Inputs:
  1. transects.geojson
  2. tokens.env  (AWS / Copernicus credentials)
  3. config.json

Produces fields:
  label
  elevation_value
  elevation_score        (1–5)
  elevation_label
  elevation_color
  geometry

Output:
  output_data/transects_with_elevation.geojson
"""

import os
import sys
import json
import math
import tempfile
import numpy as np
import geopandas as gpd
import xarray as xr
import rioxarray
import boto3
from dotenv import load_dotenv
from shapely.geometry import mapping
from pathlib import Path


# -------------------------------------------------------------
# DEM tile index generator
# -------------------------------------------------------------
def calc_tiles(minx, miny, maxx, maxy):
    def rd(v, step): return math.floor(v / step) * step
    def ru(v, step): return math.ceil(v / step) * step

    tiles = []
    for lat in range(rd(miny, 1), ru(maxy, 1)):
        for lon in range(rd(minx, 1), ru(maxx, 1)):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tiles.append(f"{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00")
    return tiles


# -------------------------------------------------------------
# Classification helper
# -------------------------------------------------------------
def classify_elevation(value, thresholds):
    if value is None or np.isnan(value):
        return None, None, "gray"
    for spec in thresholds:
        if value >= spec["min"] and value < spec["max"]:
            return spec["rank"], spec["label"], spec["color"]
    return None, None, "gray"


# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    if len(sys.argv) < 5:
        print("Usage: compute_elevation.py <transects.geojson> <tokens.env> <config.json> <output_dir>")
        sys.exit(1)

    transects_fp = Path(sys.argv[1])
    tokens_fp    = Path(sys.argv[2])
    config_fp    = Path(sys.argv[3])
    output_dir   = Path(sys.argv[4]).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "transects_with_elevation.geojson"

    # ---------------------------------------------------------
    # Load transects
    # ---------------------------------------------------------
    print("🔹 Loading transects ...")
    gdf = gpd.read_file(transects_fp)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    if "label" not in gdf.columns:
        if "id" in gdf.columns:
            gdf["label"] = gdf["id"]
        else:
            gdf["label"] = [f"T{i+1}" for i in range(len(gdf))]

    # ---------------------------------------------------------
    # Load configuration
    # ---------------------------------------------------------
    print("🔹 Loading configuration ...")
    with open(config_fp, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    elev_cfg = cfg["elevation"]["classes"]
    palette  = cfg["meta"]["default_palette"]

    thresholds = []
    for rank, spec in elev_cfg.items():
        vmin  = -np.inf if spec.get("min") is None else spec["min"]
        vmax  =  np.inf if spec.get("max") is None else spec["max"]
        color = palette[str(spec.get("palette", rank))]["color"]
        thresholds.append({
            "rank": int(rank),
            "min": vmin,
            "max": vmax,
            "label": spec["label"],
            "color": color
        })

    # ---------------------------------------------------------
    # Load S3 credentials
    # ---------------------------------------------------------
    print("🔹 Loading S3 credentials ...")
    load_dotenv(tokens_fp)

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"),
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "https://eodata.dataspace.copernicus.eu")
    )

    BUCKET_NAME = "eodata"

    # ---------------------------------------------------------
    # Determine DEM tiles
    # ---------------------------------------------------------
    bbox = gdf.to_crs("EPSG:4326").total_bounds
    tiles = calc_tiles(*bbox)
    print("🔹 DEM tiles covering AOI:", tiles)

    # ---------------------------------------------------------
    # Download tiles
    # ---------------------------------------------------------
    datasets = []
    for tile in tiles:
        dem_key = (
            "auxdata/CopDEM_COG/copernicus-dem-30m/"
            f"Copernicus_DSM_COG_10_{tile}_DEM/"
            f"Copernicus_DSM_COG_10_{tile}_DEM.tif"
        )
        print("  ↳ Fetching:", dem_key)

        tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
        try:
            s3.download_file(BUCKET_NAME, dem_key, tmpf.name)
            datasets.append(rioxarray.open_rasterio(tmpf.name, masked=True).squeeze())
            print("    ✔ downloaded")
        except Exception as e:
            print(f"    ⚠ skipped ({e})")

    if not datasets:
        print("❌ No DEM tiles available — cannot compute elevation.")
        sys.exit(1)

    # ---------------------------------------------------------
    # Merge tiles
    # ---------------------------------------------------------
    print("🔹 Merging DEM tiles ...")
    dem = xr.combine_by_coords(datasets, combine_attrs="override")

    if dem.rio.crs is None:
        dem = dem.rio.write_crs("EPSG:4326")

    # ---------------------------------------------------------
    # Reproject transects to DEM CRS
    # ---------------------------------------------------------
    tr_proj = gdf.to_crs(dem.rio.crs)

    # ---------------------------------------------------------
    # Clip DEM using 500m buffer
    # ---------------------------------------------------------
    print("🔹 Clipping DEM around transects (buffer=500m) ...")
    tr_m  = tr_proj.to_crs(3857)
    clip_geom = tr_m.buffer(500).to_crs(4326).geometry.apply(mapping)
    dem_clip = dem.rio.clip(clip_geom, crs="EPSG:4326")

    # ---------------------------------------------------------
    # Compute MAX elevation
    # ---------------------------------------------------------
    print("🔹 Computing MAX elevation ...")
    elev_values, elev_labels, elev_ranks, elev_colors = [], [], [], []

    for geom in tr_proj.geometry:
        try:
            masked = dem_clip.rio.clip([mapping(geom)], drop=True)
            valid  = masked.data[~np.isnan(masked.data)]
            max_val = float(np.max(valid)) if valid.size else None
        except Exception:
            max_val = None

        rank, label, color = classify_elevation(max_val, thresholds)

        elev_values.append(max_val)
        elev_ranks.append(rank)
        elev_labels.append(label)
        elev_colors.append(color)

    gdf["elevation_value"] = elev_values
    gdf["elevation_score"] = elev_ranks
    gdf["elevation_label"] = elev_labels
    gdf["elevation_color"] = elev_colors

    # ---------------------------------------------------------
    # Save output
    # ---------------------------------------------------------
    out_cols = [
        "label",
        "geometry",
        "elevation_value",
        "elevation_score",
        "elevation_label",
        "elevation_color",
    ]

    gdf[out_cols].to_file(out_path, driver="GeoJSON")
    print(f"✅ Saved elevation → {out_path}")


if __name__ == "__main__":
    main()
