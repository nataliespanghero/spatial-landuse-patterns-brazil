from pathlib import Path
import geopandas as gpd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
OUT_DIR = PROJECT_ROOT / "app" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

IN_GEOJSON = DATA_PROCESSED / "h3_res6_pantanal_clusters.geojson"
OUT_GEOJSON = OUT_DIR / "pantanal_h3_res6_clusters.geojson"

KEEP_COLS = [
    "h3_id", "cluster_id",
    "p_wetland", "p_tree", "p_shrub_grass", "p_water", "p_cropland",
    "bio1_mean_c", "bio12_mean_mm",
    "geometry",
]

gdf = gpd.read_file(IN_GEOJSON)
gdf = gdf[KEEP_COLS].copy()

# Simplifica geometria (ajuste tolerance se quiser mais leve)
gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.001, preserve_topology=True)

gdf.to_file(OUT_GEOJSON, driver="GeoJSON")
print("OK:", OUT_GEOJSON)
