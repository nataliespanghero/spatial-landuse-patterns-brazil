from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterstats import zonal_stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_RAW = PROJECT_ROOT / "data" / "raw"

AOI_NAME = "pantanal"
H3_RES = 6

HEX_PATH = DATA_PROCESSED / f"h3_res{H3_RES}_{AOI_NAME}.parquet"
WC_RASTER = DATA_RAW / "worldcover" / "worldcover_2021_pantanal.tif"  # ajuste o nome
OUT_PATH = DATA_PROCESSED / f"features_worldcover_{AOI_NAME}.parquet"


# ESA WorldCover 2021 classes:
# 10 Tree cover
# 20 Shrubland
# 30 Grassland
# 40 Cropland
# 50 Built-up
# 60 Bare / sparse vegetation
# 70 Snow and ice
# 80 Permanent water bodies
# 90 Herbaceous wetland
# 95 Mangroves
# 100 Moss and lichen
#
# Macroclasses para “vender” melhor (e clusterizar mais estável)
MACRO_MAP = {
    "p_tree": {10},
    "p_shrub_grass": {20, 30},
    "p_cropland": {40},
    "p_built": {50},
    "p_bare": {60},
    "p_water": {80},
    "p_wetland": {90, 95},
    "p_other": {70, 100},  # deve ser ~0 no Pantanal
}


def main() -> None:
    
    print("▶️ Starting WorldCover aggregation...")
    print(f"HEX_PATH: {HEX_PATH}")
    print(f"WC_RASTER: {WC_RASTER}")

    if not HEX_PATH.exists():
        raise FileNotFoundError(f"Hex grid não encontrado: {HEX_PATH}")
    if not WC_RASTER.exists():
        raise FileNotFoundError(f"Raster WorldCover não encontrado: {WC_RASTER}")

    gdf = gpd.read_parquet(HEX_PATH)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
        
    print(f"Hexes loaded: {len(gdf):,}")
    print("▶️ Running zonal_stats(categorical=True)... (this can take a while)")


    # Zonal stats categórico: retorna dict de {valor_classe: contagem_pixels}
    zs = zonal_stats(
        gdf,
        str(WC_RASTER),
        categorical=True,
        all_touched=True,
        nodata=None,
        geojson_out=False,
    )
    
    print("✅ zonal_stats finished.")


    df = pd.DataFrame({"h3_id": gdf["h3_id"].values})

    # total de pixels válidos por hex
    totals = []
    for d in zs:
        if d is None:
            totals.append(0)
        else:
            totals.append(int(sum(d.values())))
    df["px_total"] = totals

    # proporções por macroclasse
    for col, classes in MACRO_MAP.items():
        vals = []
        for d in zs:
            if not d:
                vals.append(0)
            else:
                vals.append(int(sum(d.get(c, 0) for c in classes)))
        df[col] = vals

    # converte contagem -> proporção (evita divisão por zero)
    prop_cols = list(MACRO_MAP.keys())
    df[prop_cols] = df[prop_cols].div(df["px_total"].replace(0, np.nan), axis=0).fillna(0.0)

    # sanity checks
    df["p_sum"] = df[prop_cols].sum(axis=1)
    # p_sum pode ficar < 1 por conta de nodata/bordas; mas não deve explodir > 1
    if (df["p_sum"] > 1.01).any():
        bad = df.loc[df["p_sum"] > 1.01, ["h3_id", "p_sum"]].head()
        raise ValueError(f"Proporções > 1 detectadas. Exemplo:\n{bad}")

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)

    print("✅ WorldCover features geradas.")
    print(f"   - Output: {OUT_PATH}")
    print(f"   - Hexes: {len(df):,}")
    print("   - Mean proportions:")
    print(df[prop_cols].mean().sort_values(ascending=False))


if __name__ == "__main__":
    main()
