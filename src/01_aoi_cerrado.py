from __future__ import annotations

from pathlib import Path
import geopandas as gpd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

BIOMES_PATH = PROJECT_ROOT / "data" / "raw" / "ibge_biomas.gpkg"
BIOMES_LAYER = None  # se for gpkg e tiver layer específico, coloque o nome aqui

AOI_NAME = "Cerrado"

OUT_GPKG = DATA_PROCESSED / "aoi_cerrado.gpkg"
OUT_GPQ = DATA_PROCESSED / "aoi_cerrado.parquet"


def _find_biome_column(gdf: gpd.GeoDataFrame) -> str:
    """
    Tenta achar automaticamente a coluna do nome do bioma.
    Ajuste aqui se o seu arquivo tiver um campo conhecido.
    """
    candidates = [
        "bioma",
        "BIOMA",
        "nome",
        "NOME",
        "name",
        "NAME",
        "Bioma",
        "NM_BIOMA",
        "NM_BIOM",
    ]
    for c in candidates:
        if c in gdf.columns:
            return c
    # fallback: procura alguma coluna string que contenha 'cerrado'
    for c in gdf.columns:
        if gdf[c].dtype == "object":
            sample = gdf[c].astype(str).str.lower()
            if sample.str.contains("cerrado").any():
                return c
    raise ValueError(
        f"Não consegui identificar a coluna do nome do bioma. Colunas: {list(gdf.columns)}"
    )


def main() -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

    if not BIOMES_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {BIOMES_PATH}\n"
            "Coloque o arquivo de biomas em data/raw e ajuste BIOMES_PATH."
        )

    if BIOMES_PATH.suffix.lower() == ".gpkg" and BIOMES_LAYER:
        gdf = gpd.read_file(BIOMES_PATH, layer=BIOMES_LAYER)
    else:
        gdf = gpd.read_file(BIOMES_PATH)

    if gdf.empty:
        raise ValueError("O arquivo de biomas foi lido, mas está vazio.")

    name_col = _find_biome_column(gdf)

    # Filtra Cerrado (case-insensitive)
    mask = gdf[name_col].astype(str).str.strip().str.lower().eq(AOI_NAME.lower())
    aoi = gdf.loc[mask].copy()

    if aoi.empty:
        # fallback: contains
        mask2 = gdf[name_col].astype(str).str.lower().str.contains(AOI_NAME.lower())
        aoi = gdf.loc[mask2].copy()

    if aoi.empty:
        raise ValueError(
            f"Não encontrei registros para '{AOI_NAME}'. "
            f"Confira o valor no campo '{name_col}'."
        )

    # CRS → WGS84 (para compatibilidade com H3 depois)
    if aoi.crs is None:
        raise ValueError("O arquivo de biomas está sem CRS. Defina o CRS antes de continuar.")
    aoi = aoi.to_crs("EPSG:4326")

    # dissolve -> geometria única
    aoi["__dissolve__"] = 1
    aoi = aoi.dissolve(by="__dissolve__", as_index=False).drop(columns=["__dissolve__"])

    # “limpeza” geométrica simples
    aoi["geometry"] = aoi.geometry.buffer(0)

    # QA básico
    if aoi.geometry.is_empty.any():
        raise ValueError("AOI resultou em geometria vazia após dissolve/clean.")
    if not aoi.geometry.is_valid.all():
        # buffer(0) resolve a maioria; se ainda inválido, alerta
        raise ValueError("AOI ainda contém geometria inválida. Precisa de correção adicional.")
    if len(aoi) != 1:
        # pode ocorrer multiparte; mantemos como 1 linha com MultiPolygon
        pass

    # Salva
    aoi.to_file(OUT_GPKG, layer="aoi", driver="GPKG")
    aoi.to_parquet(OUT_GPQ, index=False)

    bounds = aoi.total_bounds  # minx, miny, maxx, maxy
    print("✅ AOI Cerrado gerado com sucesso.")
    print(f"   - GPKG: {OUT_GPKG}")
    print(f"   - GeoParquet: {OUT_GPQ}")
    print(f"   - Bounds (WGS84): {bounds}")


if __name__ == "__main__":
    main()
