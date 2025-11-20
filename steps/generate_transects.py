#!/usr/bin/env python3
"""
Generate Transects from Coastline
---------------------------------
This CWL-ready version preserves the FULL logic from the original notebook:

  • Greedy nearest-neighbor stitching of coastline segments
  • Reprojection to EPSG:3857 for metric operations
  • Generate transects every <spacing> meters along first <max_length_m> meters
  • Preserve debug prints, comments, and processed-length messages
  • Save GeoJSON to output_data/transects.geojson

Inputs:
  1. coastline.gpkg (from extract_coastline.py)
Outputs:
  output_data/transects.geojson
"""

import os
import sys
import uuid
import math
import numpy as np
import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path


# -------------------------------------------------
# Greedy nearest-neighbor stitching
# -------------------------------------------------
def order_segments(segments):
    unused = list(segments)

    # pick starting segment (westernmost start)
    start_idx = min(range(len(unused)), key=lambda i: unused[i].coords[0][0])
    current = unused.pop(start_idx)
    ordered_coords = list(current.coords)

    while unused:
        end_point = ordered_coords[-1]

        best_idx, best_dist, best_flip = None, 1e12, False

        for i, seg in enumerate(unused):
            d_start = np.hypot(seg.coords[0][0] - end_point[0],
                               seg.coords[0][1] - end_point[1])

            d_end = np.hypot(seg.coords[-1][0] - end_point[0],
                             seg.coords[-1][1] - end_point[1])

            if d_start < best_dist:
                best_idx, best_dist, best_flip = i, d_start, False

            if d_end < best_dist:
                best_idx, best_dist, best_flip = i, d_end, True

        seg = unused.pop(best_idx)
        coords = list(seg.coords)
        if best_flip:
            coords = coords[::-1]

        ordered_coords.extend(coords[1:])

    return LineString(ordered_coords)


# -------------------------------------------------
# Generate transects
# -------------------------------------------------
def generate_transects_from_coastline(
    coastline_gdf,
    spacing=50,
    length=400,
    max_length_m=15000,
    out_path="transects.geojson",
):
    coast = coastline_gdf.to_crs(3857)

    merged = order_segments([
        g for g in coast.geometry
        if isinstance(g, LineString) and not g.is_empty
    ])

    line_length = merged.length
    used_length = min(max_length_m, line_length)

    num_pts = int(used_length // spacing)
    truncated = LineString([
        merged.interpolate(d)
        for d in np.linspace(0, used_length, num_pts + 1)
    ])

    transects = []
    for i in range(num_pts + 1):
        d = i * spacing
        if d >= truncated.length:
            continue

        point = truncated.interpolate(d)
        tangent = truncated.interpolate(min(d + 1, truncated.length)).coords[0]

        dx = tangent[0] - point.x
        dy = tangent[1] - point.y
        norm = math.sqrt(dx**2 + dy**2)
        if norm == 0:
            continue
        dx, dy = dx / norm, dy / norm

        nx, ny = -dy, dx
        half = length / 2

        p1 = (point.x - nx * half, point.y - ny * half)
        p2 = (point.x + nx * half, point.y + ny * half)
        transects.append(LineString([p1, p2]))

    # save
    out_dir = Path(os.path.dirname(out_path))
    out_dir.mkdir(parents=True, exist_ok=True)

    transects_gdf = gpd.GeoDataFrame(geometry=transects, crs=3857).to_crs(4326)
    transects_gdf["label"] = [f"T{i+1}" for i in range(len(transects_gdf))]
    transects_gdf["processed_length_km"] = used_length / 1000
    transects_gdf.to_file(out_path, driver="GeoJSON")

    print(
        f"Processed coastline distance: {used_length/1000:.2f} km "
        f"(of total {line_length/1000:.2f} km)"
    )
    print(f"✅ Saved {len(transects_gdf)} transects → {out_path}")


# -------------------------------------------------
# CLI Wrapper
# -------------------------------------------------
def main():
    if len(sys.argv) < 3:
        print("Usage: generate_transects.py <coastline.gpkg> <output_dir>")
        sys.exit(1)

    input_fp = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = output_dir / "transects.geojson"

    print("🔹 Reading coastline geometry ...")
    gdf = gpd.read_file(input_fp)

    if gdf.empty:
        print("⚠️ Coastline is empty; writing empty GeoJSON.")
        empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        empty.to_file(out_path, driver="GeoJSON")
        sys.exit(0)

    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)

    print("🔹 Generating transects ...")
    generate_transects_from_coastline(
        gdf,
        spacing=50,
        length=400,
        max_length_m=15000,
        out_path=str(out_path),
    )

    print(f"✅ Transects saved to {out_path}")


if __name__ == "__main__":
    main()
