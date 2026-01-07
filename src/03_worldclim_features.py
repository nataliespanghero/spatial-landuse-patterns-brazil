from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from rasterstats import zonal_stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_RAW = PROJECT_ROOT / "data" / "raw"

H3_RES = 6
HEX_PATH = DATA_PROCESSED / f"h3_res{H3_RES}_cerrado.parquet"

# Coloque seus GeoTIFFs aqui:
# data/raw/worldclim/
WORLDCLIM_DIR = DATA_RAW / "worldclim"

BIO1_TIF = WORLDCLIM_DIR / "wc2.1_2.5m_bio_1.tif"   # bio1 (temp média anual)
BIO12_TIF = WORLDCLIM_DIR / "wc2.1_2.5m_bio_12.tif"  # bio12 (prec anual)

OUT_PATH = DATA_PROCESSED / "features_worldclim.parquet"


def _zs_mean(gdf: gpd.GeoDataFrame, raster_path: Path, prefix: str) -> pd.Series:
    if not raster_path.exists():
        raise FileNotFoundError(f"Raster não encontrado: {raster_path}")

    stats = zonal_stats(
        gdf,
        str(raster_path),
        stats=["mean"],
        nodata=None,
        all_touched=True,  # importante p/ hex e bordas
        geojson_out=False,
    )
    return pd.Series([x["mean"] for x in stats], name=f"{prefix}_mean")


def main() -> None:
    if not HEX_PATH.exists():
        raise FileNotFoundError(f"Hex grid não encontrado: {HEX_PATH}")

    gdf = gpd.read_parquet(HEX_PATH)

    # WorldClim geralmente está em WGS84; manter EPSG:4326
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    df = gdf[["h3_id"]].copy()

    # bio1 é temperatura * 10 em WorldClim. Duas versões:
    bio1_mean_raw = _zs_mean(gdf, BIO1_TIF, "bio1")
    df["bio1_mean_raw"] = bio1_mean_raw
    df["bio1_mean_c"] = df["bio1_mean_raw"] / 10.0  # °C

    bio12_mean = _zs_mean(gdf, BIO12_TIF, "bio12")
    df["bio12_mean_mm"] = bio12_mean  # mm

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)

    print("✅ WorldClim features geradas.")
    print(f"   - Output: {OUT_PATH}")
    print("   - Colunas:", list(df.columns))
    print(df.describe(include="all").transpose().head(20))


if __name__ == "__main__":
    main()
