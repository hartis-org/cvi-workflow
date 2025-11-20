#!/usr/bin/env python3
"""
Extract Coastline
-----------------
Reads AOI CSV, queries OSM Nominatim + Overpass API for coastline geometries,
and saves results as GeoPackage (output_data/coastline.gpkg).

Workflow:
1. Read AOI CSV
2. Randomly pick AOIs (up to max_attempts)
3. Query Nominatim for bbox (with fallbacks)
4. Query Overpass for coastline
5. Save coastline as GeoPackage
"""

#!/usr/bin/env python3
import sys
import uuid
import requests
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import shape
import random


# -------------------------------
# 1. Query OSM Nominatim
# -------------------------------
def query_nominatim(place_query: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place_query, "format": "json", "limit": 1}
    headers = {
        "User-Agent": "CVI-Workflow/1.0 (https://hartis.org/contact)",
        "Accept-Language": "en",
    }
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


# -------------------------------
# 2. Pick random AOI
# -------------------------------
def get_random_aoi(df):
    row = df.sample(1).iloc[0]
    place_query = f"{row['name']}, {row['country']}"

    print(f"🔹 Trying AOI: {place_query}")

    results = []
    try:
        results = query_nominatim(place_query)
    except Exception as e:
        print(f"⚠️ Nominatim query failed: {e}")

    if not results:
        for suffix in [" Beach", " Harbor", " Bay", " Coast"]:
            if row["name"].endswith(suffix):
                base_name = row["name"].replace(suffix, "")
                fallback_query = f"{base_name}, {row['country']}"
                print(f"🔹 Trying fallback query: {fallback_query}")
                try:
                    results = query_nominatim(fallback_query)
                    if results:
                        place_query = fallback_query
                        break
                except Exception:
                    pass

    if not results:
        print(f"⚠️ Nominatim returned no bbox for {place_query}")
        return None

    res = results[0]

    bbox = {
        "min_lat": float(res["boundingbox"][0]),
        "max_lat": float(res["boundingbox"][1]),
        "min_lon": float(res["boundingbox"][2]),
        "max_lon": float(res["boundingbox"][3]),
    }

    return {
        "process_type": "CVI calculation",
        "area": place_query,
        "bounding_box": bbox,
        "uuid": str(uuid.uuid4()),
    }


# -------------------------------
# 3. Overpass coastline
# -------------------------------
def query_overpass(bbox):
    query = f"""
    [out:json];
    way["natural"="coastline"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
    out geom;
    """
    url = "https://overpass-api.de/api/interpreter"
    r = requests.post(url, data={"data": query}, timeout=60)
    r.raise_for_status()
    return r.json()


# -------------------------------
# 4. Retry until coastline found
# -------------------------------
def try_get_random_aoi_with_coastline(df, max_attempts=5):
    for attempt in range(max_attempts):
        print(f"\n===== Attempt {attempt + 1} of {max_attempts} =====")
        aoi = get_random_aoi(df)
        if aoi is None:
            print("⚠️ Failed to get valid bbox, trying next AOI...")
            continue

        try:
            coastline_json = query_overpass(aoi["bounding_box"])
        except Exception as e:
            print(f"⚠️ Overpass error: {e}")
            continue

        features = []
        for el in coastline_json.get("elements", []):
            if "geometry" in el:
                coords = [(pt["lon"], pt["lat"]) for pt in el["geometry"]]
                features.append({"type": "LineString", "coordinates": coords})

        if features:
            print(f"✅ Coastline found for {aoi['area']}")
            gdf = gpd.GeoDataFrame(
                geometry=[shape(f) for f in features], crs="EPSG:4326"
            )
            return aoi, gdf

        print(f"⚠️ No coastline for {aoi['area']}")

    raise RuntimeError("❌ No valid AOI with coastline found after all attempts.")


# -------------------------------
# 5. Zoom estimation
# -------------------------------
def calculate_zoom_level(bbox: dict) -> int:
    lat_diff = bbox["max_lat"] - bbox["min_lat"]
    lon_diff = bbox["max_lon"] - bbox["min_lon"]
    max_diff = max(lat_diff, lon_diff)

    if max_diff > 10: zoom = 6
    elif max_diff > 5: zoom = 7
    elif max_diff > 2: zoom = 8
    elif max_diff > 1: zoom = 9
    elif max_diff > 0.5: zoom = 10
    elif max_diff > 0.25: zoom = 11
    elif max_diff > 0.1: zoom = 12
    else: zoom = 13

    print(f"Calculated zoom level: {zoom} (bbox span ≈ {max_diff:.3f}°)")
    return zoom


# -------------------------------
# 6. MAIN
# -------------------------------
def main():
    if len(sys.argv) < 3:
        print("Usage: extract_coastline.py <aoi_csv> <output_dir>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    out_gpkg = output_dir / "coastline.gpkg"

    print(f"🔹 Reading AOI CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    if df.empty:
        print("❌ AOI CSV is empty.")
        sys.exit(1)

    try:
        aoi, coastline_gdf = try_get_random_aoi_with_coastline(df)
    except Exception as e:
        print(e)
        empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        empty.to_file(out_gpkg, layer="coastline", driver="GPKG")
        sys.exit(0)

    zoom = calculate_zoom_level(aoi["bounding_box"])
    print("You can reuse zoom level:", zoom)

    coastline_gdf.to_file(out_gpkg, layer="coastline", driver="GPKG")
    print(f"✅ Saved coastline: {out_gpkg}")


if __name__ == "__main__":
    main()
