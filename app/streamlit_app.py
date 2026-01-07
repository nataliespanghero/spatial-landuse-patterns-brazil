from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

HEX_GEOJSON = DATA_PROCESSED / "h3_res6_cerrado.geojson"
FEAT_WC = DATA_PROCESSED / "features_worldclim.parquet"


@st.cache_data
def load_data():
    gdf = gpd.read_file(HEX_GEOJSON)
    df = pd.read_parquet(FEAT_WC)
    gdf = gdf.merge(df, on="h3_id", how="left")
    return gdf


def main():
    st.set_page_config(page_title="Brazil Cerrado – Environmental Drivers (H3)", layout="wide")
    st.title("Brazil Cerrado — Environmental Drivers (H3 res 6)")
    st.caption("WorldClim features aggregated to H3 hexagons.")

    gdf = load_data()

    metric = st.selectbox(
        "Select metric",
        ["bio12_mean_mm", "bio1_mean_c"],
        index=0,
    )

    # Center map
    centroid = gdf.unary_union.centroid
    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=5, tiles="CartoDB positron")

    # Choropleth
    folium.Choropleth(
        geo_data=gdf.to_json(),
        data=gdf[["h3_id", metric]],
        columns=["h3_id", metric],
        key_on="feature.properties.h3_id",
        fill_opacity=0.7,
        line_opacity=0.1,
        legend_name=metric,
    ).add_to(m)

    # Tooltip layer (light)
    folium.GeoJson(
        gdf,
        tooltip=folium.GeoJsonTooltip(
            fields=["h3_id", "bio1_mean_c", "bio12_mean_mm"],
            aliases=["H3:", "Temp (°C):", "Precip (mm):"],
            localize=True,
        ),
        name="tooltips",
    ).add_to(m)

    st_folium(m, width=1200, height=700)


if __name__ == "__main__":
    main()
