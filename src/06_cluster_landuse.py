from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

AOI_NAME = "pantanal"
H3_RES = 6

HEX_GEOJSON = DATA_PROCESSED / f"h3_res{H3_RES}_{AOI_NAME}.geojson"
LULC_FEAT = DATA_PROCESSED / f"features_worldcover_{AOI_NAME}.parquet"
WC_FEAT = DATA_PROCESSED / "features_worldclim.parquet"

OUT_TABLE = DATA_PROCESSED / f"clusters_{AOI_NAME}.parquet"
OUT_GEOJSON = DATA_PROCESSED / f"h3_res{H3_RES}_{AOI_NAME}_clusters.geojson"


def main() -> None:
    for p in [HEX_GEOJSON, LULC_FEAT, WC_FEAT]:
        if not p.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {p}")

    lulc = pd.read_parquet(LULC_FEAT)
    wc = pd.read_parquet(WC_FEAT)[["h3_id", "bio1_mean_c", "bio12_mean_mm"]]

    df = lulc.merge(wc, on="h3_id", how="left")

    # Features para cluster (LULC é o núcleo; clima entra como “contexto”)
    lulc_cols = [
        "p_tree", "p_shrub_grass", "p_cropland", "p_built",
        "p_bare", "p_water", "p_wetland", "p_other",
    ]
    # opcional: incluir clima no cluster (eu deixaria fora por enquanto)
    use_climate_in_cluster = False
    climate_cols = ["bio1_mean_c", "bio12_mean_mm"]

    feat_cols = lulc_cols + (climate_cols if use_climate_in_cluster else [])

    X = df[feat_cols].to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=0.0)

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    # Escolha de K (rápido e defensável)
    k_candidates = [4, 5, 6, 7, 8]
    best_k, best_score = None, -1
    for k in k_candidates:
        model = KMeans(n_clusters=k, n_init=20, random_state=42)
        labels = model.fit_predict(Xs)
        score = silhouette_score(Xs, labels)
        if score > best_score:
            best_k, best_score = k, score

    kmeans = KMeans(n_clusters=best_k, n_init=30, random_state=42)
    df["cluster_id"] = kmeans.fit_predict(Xs).astype(int)
    df["cluster_k"] = int(best_k)
    df["silhouette"] = float(best_score)

    # Perfil dos clusters (ótimo pra README e pra “contar história”)
    profile = (
        df.groupby("cluster_id")[lulc_cols + climate_cols]
        .mean()
        .sort_index()
    )

    df.to_parquet(OUT_TABLE, index=False)

    # GeoJSON para app (hex + cluster)
    gdf = gpd.read_file(HEX_GEOJSON)
    gdf = gdf.merge(df[["h3_id", "cluster_id"] + lulc_cols + climate_cols], on="h3_id", how="left")
    gdf.to_file(OUT_GEOJSON, driver="GeoJSON")

    print("✅ Clusters gerados.")
    print(f"   - k escolhido: {best_k} (silhouette={best_score:.3f})")
    print(f"   - tabela: {OUT_TABLE}")
    print(f"   - geojson: {OUT_GEOJSON}")
    print("\n📌 Cluster profiles (means):")
    print(profile.round(3))


if __name__ == "__main__":
    main()
