#!/usr/bin/env python3
"""
Compute Slope for Coastal Transects (Corrected)
-----------------------------------------------
1. Downloads DEM tiles (EPSG:4326).
2. Reprojects DEM to Metric CRS (EPSG:3035) for accurate slope calc.
3. Computes Slope %.
4. Ranks based on config.
"""

import os
import sys
import json
import math
import tempfile
import numpy as np
import geopandas as gpd
import rioxarray
import xarray as xr
import boto3
from shapely.geometry import mapping
from pathlib import Path
from dotenv import load_dotenv
import warnings

# Suppress GeoPandas warning about buffering in degrees
warnings.filterwarnings("ignore", message=".*Geometry is in a geographic CRS.*")
# Suppress FutureWarnings often thrown by xarray/rioxarray
warnings.filterwarnings("ignore", category=FutureWarning)

# -----------------------------------------------------------
# DEM tile helper
# -----------------------------------------------------------
def calculate_dem_tiles(minx, miny, maxx, maxy):
    def rd(v, step): return math.floor(v / step) * step
    def ru(v, step): return math.ceil(v / step) * step

    tiles = []
    for lat in range(rd(miny, 1), ru(maxy, 1)):
        for lon in range(rd(minx, 1), ru(maxx, 1)):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tiles.append(f"{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00")
    return tiles

# -----------------------------------------------------------
# Slope classification
# -----------------------------------------------------------
def build_slope_thresholds(cfg):
    slope_cfg = cfg["slope"]["classes"]
    palette = cfg["meta"]["default_palette"]

    thresholds = []
    for rank, spec in slope_cfg.items():
        thresholds.append({
            "rank": int(rank),
            "min": -np.inf if spec.get("min") is None else spec["min"],
            "max":  np.inf if spec.get("max") is None else spec["max"],
            "label": spec["label"],
            "color": palette[str(spec["palette"])]["color"]
        })
    return thresholds

def classify_slope(value, thresholds):
    if value is None or np.isnan(value):
        return None, None, "gray"
    for spec in thresholds:
        # Standard logic: min <= val < max
        if spec["min"] <= value < spec["max"]:
            return spec["rank"], spec["label"], spec["color"]
    return None, None, "gray"

# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------
def main():
    if len(sys.argv) < 5:
        print("Usage: compute_slope.py <transects.geojson> <tokens.env> <config.json> <output_dir>")
        sys.exit(1)

    transects_fp = Path(sys.argv[1])
    tokens_fp    = Path(sys.argv[2])
    config_fp    = Path(sys.argv[3])
    out_dir      = Path(sys.argv[4]).resolve()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_fp = out_dir / "transects_with_slope.geojson"

    print("🔹 Output directory:", out_dir)

    # 1. Load transects
    print("🔹 Loading transects ...")
    tr = gpd.read_file(transects_fp)
    if tr.crs is None:
        tr = tr.set_crs("EPSG:4326")

    if "label" not in tr.columns:
        if "id" in tr.columns:
            tr["label"] = tr["id"]
        else:
            tr["label"] = [f"T{i+1}" for i in range(len(tr))]

    # 2. Load config
    print("🔹 Loading config ...")
    with open(config_fp, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    thresholds = build_slope_thresholds(cfg)

    # 3. Load tokens
    print("🔹 Loading tokens ...")
    load_dotenv(tokens_fp)

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"),
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "https://eodata.dataspace.copernicus.eu")
    )
    BUCKET_NAME = "eodata"

    # 4. Determine DEM tiles
    minx, miny, maxx, maxy = tr.to_crs("EPSG:4326").total_bounds
    tiles = calculate_dem_tiles(minx, miny, maxx, maxy)
    print("Tiles covering AOI:", tiles)

    # 5. Download tiles
    datasets = []
    for tile in tiles:
        key = (
            "auxdata/CopDEM_COG/copernicus-dem-30m/"
            f"Copernicus_DSM_COG_10_{tile}_DEM/"
            f"Copernicus_DSM_COG_10_{tile}_DEM.tif"
        )
        print("  Fetching:", key)
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
            s3.download_file(BUCKET_NAME, key, tmp.name)
            ds = rioxarray.open_rasterio(tmp.name, masked=True).squeeze()
            datasets.append(ds)
        except Exception as e:
            print(f"   ⚠️ Failed: {e}")

    if not datasets:
        print("❌ No DEM tiles downloaded.")
        sys.exit(1)

    # 6. Merge DEM
    print("🔹 Merging DEM tiles ...")
    dem = xr.combine_by_coords(datasets, combine_attrs="override")
    if dem.rio.crs is None:
        dem = dem.rio.write_crs("EPSG:4326")

    # ===========================================================
    # CRITICAL FIX: Reproject to Metric CRS (EPSG:3035)
    # ===========================================================
    print("🔹 Reprojecting DEM to meters (EPSG:3035) ...")
    # EPSG:3035 is ETRS89-extended / LAEA Europe - excellent for Med area
    # You can also use 3857 (Web Mercator) if 3035 fails, but 3035 is strictly better for metric accuracy.
    metric_crs = "EPSG:3035" 
    
    # We clip to a large buffer first to speed up reprojection (reprojecting the whole tile is slow)
    tr_buffer = tr.to_crs("EPSG:4326").buffer(0.01).total_bounds # Small buffer in degrees
    dem_subset = dem.rio.clip_box(*tr_buffer)
    
    # Reproject
    dem_metric = dem_subset.rio.reproject(metric_crs, resolution=30) # Force ~30m resolution
    
    # Ensure transects match the metric CRS
    tr_metric = tr.to_crs(metric_crs)

    # 7. Compute Slope (Now in Meters/Meters)
    print("🔹 Computing slope ...")
    # Resolution is now in meters (e.g., 30.0)
    xres, yres = abs(dem_metric.rio.resolution()[0]), abs(dem_metric.rio.resolution()[1])
    
    # Gradient returns (dZ/dy, dZ/dx)
    grad_y, grad_x = np.gradient(dem_metric.data, yres, xres)
    
    # Slope = rise/run * 100
    slope = np.sqrt(grad_x**2 + grad_y**2) * 100
    
    # Create DataArray for slope
    slope_da = xr.DataArray(slope, coords=dem_metric.coords, dims=dem_metric.dims)
    slope_da.rio.write_crs(metric_crs, inplace=True)

    # 8. Classify
    print("🔹 Classifying slope ...")
    vals, ranks, labels, colors = [], [], [], []

    for geom in tr_metric.geometry:
        try:
            # Clip the slope raster to the transect line
            # This extracts pixels that intersect the line
            mask = slope_da.rio.clip([mapping(geom)], drop=True)
            valid = mask.data[~np.isnan(mask.data)]

            if valid.size == 0:
                vals.append(None); ranks.append(None)
                labels.append(None); colors.append("gray")
                continue

            mean_val = float(np.mean(valid))
            rank, label, color = classify_slope(mean_val, thresholds)

            vals.append(mean_val)
            ranks.append(rank)
            labels.append(label)
            colors.append(color)

        except Exception:
            vals.append(None); ranks.append(None)
            labels.append(None); colors.append("gray")

    # Assign back to original GeoDataFrame
    tr["slope_value"] = vals
    tr["slope_score"] = ranks
    tr["slope_label"] = labels
    tr["slope_color"] = colors

    # Save
    tr.to_file(out_fp, driver="GeoJSON")
    print(f"✅ Saved slope: {out_fp}")

if __name__ == "__main__":
    main()