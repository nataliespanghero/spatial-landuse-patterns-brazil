from __future__ import annotations

from pathlib import Path
from typing import Iterable

import geopandas as gpd
import pandas as pd
import shapely.geometry as sgeom
import h3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

AOI_GPKG = DATA_PROCESSED / "aoi_cerrado.gpkg"
AOI_LAYER = "aoi"

H3_RES = 6

OUT_GPQ = DATA_PROCESSED / f"h3_res{H3_RES}_cerrado.parquet"
OUT_GEOJSON = DATA_PROCESSED / f"h3_res{H3_RES}_cerrado.geojson"


def _aoi_to_h3shape(aoi_geom) -> h3.LatLngPoly:
    """
    Converte shapely (Polygon/MultiPolygon) para h3.LatLngPoly(s).
    Usamos lat/lng (y/x) na ordem esperada pelo h3.
    """
    if aoi_geom.geom_type == "Polygon":
        poly = aoi_geom
        exterior = [(lat, lng) for lng, lat in list(poly.exterior.coords)]
        holes = []
        for interior in poly.interiors:
            holes.append([(lat, lng) for lng, lat in list(interior.coords)])
        return h3.LatLngPoly(exterior, holes)

    if aoi_geom.geom_type == "MultiPolygon":
        # h3.polygon_to_cells aceita LatLngMultiPoly também
        polys = []
        for poly in aoi_geom.geoms:
            exterior = [(lat, lng) for lng, lat in list(poly.exterior.coords)]
            holes = []
            for interior in poly.interiors:
                holes.append([(lat, lng) for lng, lat in list(interior.coords)])
            polys.append(h3.LatLngPoly(exterior, holes))
        return h3.LatLngMultiPoly(polys)

    raise ValueError(f"Geometria AOI não suportada: {aoi_geom.geom_type}")


def _h3_to_polygon(h: str) -> sgeom.Polygon:
    coords = h3.cell_to_boundary(h)  # [(lat,lng), ...]
    # shapely usa (x,y) = (lng,lat)
    ring = [(lng, lat) for lat, lng in coords]
    return sgeom.Polygon(ring)


def main() -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    if not AOI_GPKG.exists():
        raise FileNotFoundError(
            f"AOI não encontrado em {AOI_GPKG}. Rode primeiro: src/01_aoi_cerrado.py"
        )

    aoi = gpd.read_file(AOI_GPKG, layer=AOI_LAYER)
    if aoi.empty:
        raise ValueError("AOI lido, mas está vazio.")
    if aoi.crs is None:
        raise ValueError("AOI sem CRS.")
    aoi = aoi.to_crs("EPSG:4326")

    aoi_geom = aoi.geometry.iloc[0]
    h3shape = _aoi_to_h3shape(aoi_geom)

    # cobre polígono com células H3
    cells: set[str] = h3.polygon_to_cells(h3shape, H3_RES)
    if not cells:
        raise ValueError("Nenhuma célula H3 gerada. Verifique AOI e resolução.")

    # GeoDataFrame
    df = pd.DataFrame({"h3_id": sorted(cells)})
    df["geometry"] = df["h3_id"].map(_h3_to_polygon)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

    # QA: remover hexes que não intersectam (edge cases)
    gdf = gdf[gdf.intersects(aoi_geom)].copy()

    # Área (em km²) para QA: reprojeta para um CRS métrico rápido
    # SIRGAS 2000 / Brazil Polyconic (EPSG:5880) é uma opção; mas para o Cerrado grande,
    # vale usar um equal-area global tipo EPSG:6933 para área aproximada.
    gdf_area = gdf.to_crs("EPSG:6933")
    gdf["area_km2"] = (gdf_area.area / 1_000_000).astype("float64")

    # Salva
    gdf.to_parquet(OUT_GPQ, index=False)
    gdf.to_file(OUT_GEOJSON, driver="GeoJSON")

    print("✅ Grid H3 gerado com sucesso.")
    print(f"   - Resolução: {H3_RES}")
    print(f"   - Hexes: {len(gdf):,}")
    print(f"   - GeoParquet: {OUT_GPQ}")
    print(f"   - GeoJSON (app): {OUT_GEOJSON}")
    print(
        f"   - Área km² (min/mean/max): "
        f"{gdf['area_km2'].min():.2f} / {gdf['area_km2'].mean():.2f} / {gdf['area_km2'].max():.2f}"
    )


if __name__ == "__main__":
    main()
