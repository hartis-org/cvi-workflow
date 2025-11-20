#!/usr/bin/env python3
"""
Compute the Coastal Vulnerability Index (CVI)
---------------------------------------------
Combines the results of previous steps (landcover, slope, erosion, elevation),
computes a weighted composite index, and generates both GeoJSON and Folium HTML map.

Inputs:
  1. transects_with_land_cover.geojson
  2. transects_with_slope.geojson
  3. transects_with_erosion.geojson
  4. transects_with_elevation.geojson
  5. config_json (defines scoring and weights)

Outputs:
  - output_data/transects_with_cvi_equal.geojson
  - output_data/cvi_map.html
"""

#!/usr/bin/env python3
"""
Compute the Coastal Vulnerability Index (CVI)
---------------------------------------------
"""

import sys
import os
import json
import math
import numpy as np
import geopandas as gpd
import pandas as pd
from pathlib import Path


# ----------------------------------------------------
# Helpers (unchanged)
# ----------------------------------------------------
def cvi_equal_geometric(row: pd.Series) -> float:
    vals = row.values.astype(float)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return np.nan
    return math.sqrt(np.prod(vals) / len(vals))


def classify(value, thresholds):
    if value is None or np.isnan(value):
        return None, "No Data", "gray"
    for t in thresholds:
        if value >= t["min"] and value < t["max"]:
            return t["rank"], t["label"], t["color"]
    return None, "No Data", "gray"


def build_thresholds(cfg):
    palette = cfg["meta"]["default_palette"]
    classes = cfg["total_cvi"]["fixed"]
    out = []
    for rank_str, spec in classes.items():
        rank = int(rank_str)
        vmin = -np.inf if spec.get("min") is None else spec["min"]
        vmax = np.inf if spec.get("max") is None else spec["max"]
        color = palette[str(spec["palette"])]["color"]
        out.append({
            "rank": rank,
            "min": vmin,
            "max": vmax,
            "label": spec["label"],
            "color": color
        })
    return sorted(out, key=lambda d: d["rank"])


def normalize(series):
    if series.max() == series.min():
        return series * 0
    return (series - series.min()) / (series.max() - series.min())


# ----------------------------------------------------
# Main
# ----------------------------------------------------
def main():
    if len(sys.argv) != 7:
        print("Usage: compute_cvi.py <landcover> <slope> <erosion> <elevation> <config.json> <output_dir>")
        sys.exit(1)

    land_fp     = Path(sys.argv[1])
    slope_fp    = Path(sys.argv[2])
    erosion_fp  = Path(sys.argv[3])
    elev_fp     = Path(sys.argv[4])
    config_fp   = Path(sys.argv[5])
    out_dir     = Path(sys.argv[6]).resolve()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_geojson = out_dir / "transects_with_cvi_equal.geojson"

    print("🔹 Loading inputs...")
    g_land = gpd.read_file(land_fp)
    g_slope = gpd.read_file(slope_fp)
    g_erosion = gpd.read_file(erosion_fp)
    g_elev = gpd.read_file(elev_fp)

    gdf = g_land[["label", "geometry"]].copy()

    def merge_score(df, other, col):
        if col in other.columns:
            return df.merge(other[["label", col]], on="label", how="left")
        df[col] = np.nan
        return df

    gdf = merge_score(gdf, g_land, "land_cover_score")
    gdf = merge_score(gdf, g_slope, "slope_score")
    gdf = merge_score(gdf, g_erosion, "erosion_score")
    gdf = merge_score(gdf, g_elev, "elevation_score")

    print("🔹 Computing CVI...")
    cols = ["land_cover_score", "slope_score", "erosion_score", "elevation_score"]
    gdf["CVI_equal"] = gdf[cols].apply(cvi_equal_geometric, axis=1)
    gdf["CVI_equal_norm"] = normalize(gdf["CVI_equal"])

    print("🔹 Loading config...")
    with open(config_fp, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    thresholds = build_thresholds(cfg)
    classes = [classify(v, thresholds) for v in gdf["CVI_equal"]]
    gdf["CVI_equal_class"], gdf["CVI_equal_label"], gdf["CVI_equal_color"] = zip(*classes)

    print(f"🔹 Writing output → {out_geojson}")
    gdf.to_file(out_geojson, driver="GeoJSON")

    print("✅ CVI computation complete.")


if __name__ == "__main__":
    main()
