#!/usr/bin/env python3
"""
Compute Land Cover Vulnerability for Coastal Transects
------------------------------------------------------
Extracts dominant land cover class near each transect from
ESA WorldCover, maps each class to a CVI-style rank, label,
and color, and writes a GeoJSON output.

CWL-ready version:
  Usage:
    compute_landcover.py <transects.geojson> <tokens.env> <config.json> <output_dir>

Output is always written to:
    <output_dir>/transects_with_land_cover.geojson
"""

import os
import sys
import json
import math
import boto3
import tempfile
import numpy as np
import geopandas as gpd
import rioxarray
import xarray as xr
from shapely.geometry import mapping
from pathlib import Path
from dotenv import load_dotenv
import pyproj

# Ensure PROJ works inside CWL temp dirs
os.environ["PROJ_LIB"] = pyproj.datadir.get_data_dir()
os.environ["PROJ_DATA"] = os.environ["PROJ_LIB"]


# -------------------------------------------------------------------
# Helper: ESA tile ID generation (unchanged)
# -------------------------------------------------------------------
def bbox_to_tile_ids(minx, miny, maxx, maxy):
    lon_start = int(math.floor(minx / 3.0) * 3)
    lon_end   = int(math.floor(maxx / 3.0) * 3)
    lat_start = int(math.floor(miny / 3.0) * 3)
    lat_end   = int(math.floor(maxy / 3.0) * 3)

    tile_ids = []
    for lat in range(lat_start, lat_end + 3, 3):
        for lon in range(lon_start, lon_end + 3, 3):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tile_ids.append(f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}")
    return tile_ids


# -------------------------------------------------------------------
# Land cover class decoding
# -------------------------------------------------------------------
def build_lc_lookup(cfg):
    classes = cfg["land_cover"]["classes"]
    lookup = {}
    for rank, spec in classes.items():
        for code in spec.get("codes", []):
            lookup[int(code)] = {
                "rank": int(rank),
                "label": spec["label"],
                "color": spec["color"]
            }
    return lookup


def classify_land_cover_code(code, lookup):
    if code in lookup:
        entry = lookup[code]
        return entry["rank"], entry["label"], entry["color"]
    return None, None, "gray"


# -------------------------------------------------------------------
# MAIN (CWL-ready)
# -------------------------------------------------------------------
def main():
    if len(sys.argv) < 5:
        print("Usage: compute_landcover.py <transects.geojson> <tokens.env> <config.json> <output_dir>")
        sys.exit(1)

    transects_fp = Path(sys.argv[1])
    tokens_fp    = Path(sys.argv[2])
    config_fp    = Path(sys.argv[3])
    out_dir      = Path(sys.argv[4]).resolve()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "transects_with_land_cover.geojson"

    print("🔹 Output directory:", out_dir)

    # ------------------------------------------------------------------
    # Load transects
    # ------------------------------------------------------------------
    print("🔹 Loading transects ...")
    transects_gdf = gpd.read_file(transects_fp)
    if transects_gdf.crs is None:
        transects_gdf = transects_gdf.set_crs("EPSG:4326")

    # ------------------------------------------------------------------
    # Load config JSON
    # ------------------------------------------------------------------
    print("🔹 Loading land cover config ...")
    with open(config_fp, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    LC_LOOKUP = build_lc_lookup(cfg)

    LANDCOVER_PREFIX = "auxdata/ESA_WORLD_COVER/2021/"
    BUCKET_NAME = "eodata"

    # ------------------------------------------------------------------
    # Load S3/Copernicus Dataspace tokens
    # ------------------------------------------------------------------
    print("🔹 Loading Copernicus Dataspace tokens ...")
    load_dotenv(tokens_fp)

    s3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "eu-central-1"),
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "https://eodata.dataspace.copernicus.eu")
    )

    # ------------------------------------------------------------------
    # Determine which ESA tiles cover the AOI
    # ------------------------------------------------------------------
    minx, miny, maxx, maxy = transects_gdf.to_crs("EPSG:4326").total_bounds
    tile_ids = bbox_to_tile_ids(minx, miny, maxx, maxy)
    print("🔹 Tiles covering AOI:", tile_ids)

    tile_keys = [
        f"{LANDCOVER_PREFIX}ESA_WorldCover_10m_2021_v200_{tid}/ESA_WorldCover_10m_2021_v200_{tid}_Map.tif"
        for tid in tile_ids
    ]

    # ------------------------------------------------------------------
    # Download tiles
    # ------------------------------------------------------------------
    datasets = []
    for key in tile_keys:
        try:
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
            s3.download_file(BUCKET_NAME, key, tmpfile.name)
            ds = rioxarray.open_rasterio(tmpfile.name, masked=True)
            datasets.append(ds)
            print("  ✔️ downloaded:", key)
        except Exception as e:
            print(f"  ⚠️ Could not fetch {key}: {e}")

    if not datasets:
        print("❌ No WorldCover tiles found for AOI! Cannot continue.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Merge all rasters
    # ------------------------------------------------------------------
    print("🔹 Merging tiles ...")
    merged = xr.combine_by_coords(datasets, combine_attrs="override")
    if merged.rio.crs is None:
        merged = merged.rio.write_crs("EPSG:4326")

    # ------------------------------------------------------------------
    # Reproject transects to raster CRS
    # ------------------------------------------------------------------
    if str(transects_gdf.crs) != str(merged.rio.crs):
        print("🔹 Reprojecting transects ...")
        transects_gdf = transects_gdf.to_crs(merged.rio.crs)

    # ------------------------------------------------------------------
    # Clip raster
    # ------------------------------------------------------------------
    print("🔹 Clipping raster to AOI ...")
    clipped = merged.rio.clip_box(*transects_gdf.total_bounds)

    # ------------------------------------------------------------------
    # Classify each transect
    # ------------------------------------------------------------------
    print("🔹 Classifying land cover ...")
    scores, labels, colors, codes = [], [], [], []

    for geom in transects_gdf.geometry:
        try:
            masked = clipped.rio.clip([mapping(geom)], drop=True)
            valid = masked.data[(masked.data > 0) & (masked.data != 80)]

            if valid.size == 0:
                scores.append(None); labels.append(None); colors.append("gray"); codes.append(None)
                continue

            uniq, counts = np.unique(valid, return_counts=True)
            predominant = int(uniq[np.argmax(counts)])

            rank, label, color = classify_land_cover_code(predominant, LC_LOOKUP)

            scores.append(rank)
            labels.append(label)
            colors.append(color)
            codes.append(predominant)

        except Exception:
            scores.append(None); labels.append(None); colors.append("gray"); codes.append(None)

    transects_gdf["land_cover_score"] = scores
    transects_gdf["land_cover_label"] = labels
    transects_gdf["land_cover_color"] = colors
    transects_gdf["land_cover_value"] = codes

    # ------------------------------------------------------------------
    # Save output
    # ------------------------------------------------------------------
    transects_gdf.to_file(out_path, driver="GeoJSON")
    print(f"✅ Saved land-cover annotated transects → {out_path}")


if __name__ == "__main__":
    main()
