from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

# -----------------------------
# Paths
# -----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"

HEX_GEOJSON = DATA_PROCESSED / "app" / "data" / "pantanal_h3_res6_clusters.geojson"


# -----------------------------
# Styling helpers
# -----------------------------
CLUSTER_COLORS = {
    0: "#1b9e77",
    1: "#d95f02",
    2: "#7570b3",
    3: "#e7298a",
    4: "#66a61e",
    5: "#e6ab02",
    6: "#a6761d",
    7: "#666666",
}

LAYER_LABELS = {
    "cluster_id": "Land cover clusters (KMeans)",
    "bio12_mean_mm": "Annual precipitation (mm) — WorldClim",
    "bio1_mean_c": "Annual mean temperature (°C) — WorldClim",
    "p_wetland": "Wetland proportion — WorldCover",
    "p_tree": "Tree cover proportion — WorldCover",
    "p_water": "Water proportion — WorldCover",
    "p_shrub_grass": "Shrub/grass proportion — WorldCover",
    "p_cropland": "Cropland proportion — WorldCover",
}


@st.cache_data
def load_data() -> gpd.GeoDataFrame:
    if not HEX_GEOJSON.exists():
        raise FileNotFoundError(f"GeoJSON not found: {HEX_GEOJSON}")
    gdf = gpd.read_file(HEX_GEOJSON)

    # Ensure numeric types (folium can be picky)
    numeric_cols = [
        "cluster_id",
        "bio1_mean_c",
        "bio12_mean_mm",
        "p_wetland",
        "p_tree",
        "p_water",
        "p_shrub_grass",
        "p_cropland",
    ]
    for c in numeric_cols:
        if c in gdf.columns:
            gdf[c] = pd.to_numeric(gdf[c], errors="coerce")

    return gdf


def build_cluster_summary(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    cols_needed = [
        "cluster_id",
        "h3_id",
        "p_wetland",
        "p_tree",
        "p_shrub_grass",
        "p_water",
        "p_cropland",
        "bio1_mean_c",
        "bio12_mean_mm",
    ]
    existing = [c for c in cols_needed if c in gdf.columns]
    df = gdf[existing].copy()

    if "cluster_id" not in df.columns:
        return pd.DataFrame()

    summary = (
        df.groupby("cluster_id", dropna=True)
        .agg(
            n=("h3_id", "count") if "h3_id" in df.columns else ("cluster_id", "size"),
            wetland=("p_wetland", "mean") if "p_wetland" in df.columns else ("cluster_id", "size"),
            tree=("p_tree", "mean") if "p_tree" in df.columns else ("cluster_id", "size"),
            shrub_grass=("p_shrub_grass", "mean") if "p_shrub_grass" in df.columns else ("cluster_id", "size"),
            water=("p_water", "mean") if "p_water" in df.columns else ("cluster_id", "size"),
            cropland=("p_cropland", "mean") if "p_cropland" in df.columns else ("cluster_id", "size"),
            temp_c=("bio1_mean_c", "mean") if "bio1_mean_c" in df.columns else ("cluster_id", "size"),
            precip_mm=("bio12_mean_mm", "mean") if "bio12_mean_mm" in df.columns else ("cluster_id", "size"),
        )
        .reset_index()
    )

    summary["pct"] = (summary["n"] / summary["n"].sum() * 100).round(1)

    # make it pretty
    for c in ["wetland", "tree", "shrub_grass", "water", "cropland"]:
        if c in summary.columns:
            summary[c] = summary[c].round(3)
    for c in ["temp_c", "precip_mm"]:
        if c in summary.columns:
            summary[c] = summary[c].round(2)

    return summary.sort_values("pct", ascending=False)


def make_map(gdf: gpd.GeoDataFrame, layer: str) -> folium.Map:
    # Center map
    centroid = gdf.geometry.union_all().centroid
    m = folium.Map(location=[centroid.y, centroid.x], zoom_start=5, tiles="CartoDB positron")

    # Helper for tooltip
    tooltip_fields = []
    tooltip_aliases = []

    def add_tooltip_field(field: str, label: str):
        if field in gdf.columns:
            tooltip_fields.append(field)
            tooltip_aliases.append(label)

    add_tooltip_field("h3_id", "H3:")
    add_tooltip_field("cluster_id", "Cluster:")
    add_tooltip_field("bio1_mean_c", "Temp (°C):")
    add_tooltip_field("bio12_mean_mm", "Precip (mm):")
    add_tooltip_field("p_wetland", "Wetland:")
    add_tooltip_field("p_tree", "Tree:")
    add_tooltip_field("p_water", "Water:")
    add_tooltip_field("p_cropland", "Cropland:")

    if layer == "cluster_id":
        # Discrete clusters with fixed palette
        def style_fn(feat):
            cid = feat["properties"].get("cluster_id")
            if cid is None:
                return {"fillOpacity": 0.0, "weight": 0.0}
            try:
                cid_int = int(cid)
            except Exception:
                cid_int = None
            color = CLUSTER_COLORS.get(cid_int, "#999999")
            return {
                "fillColor": color,
                "color": "#000000",
                "weight": 0.15,
                "fillOpacity": 0.55,
            }

        geo = folium.GeoJson(
            gdf,
            style_function=style_fn,
            name="clusters",
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                localize=True,
            ),
        )
        geo.add_to(m)

        # Add a simple HTML legend
        legend_items = []
        for k in sorted(CLUSTER_COLORS.keys()):
            legend_items.append(f"""
            <div style="display:flex;align-items:center;margin-bottom:4px;color:#111111;">
            <div style="width:12px;height:12px;background:{CLUSTER_COLORS[k]};
                        margin-right:8px;border:1px solid #333;"></div>
            <div>Cluster {k}</div>
            </div>
            """)
        legend_html = f"""
        <div style="
            position: fixed;
            bottom: 30px; left: 30px; z-index: 9999;
            background: rgba(255,255,255,0.95);
            color: #111111;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid rgba(0,0,0,0.3);
            box-shadow: 0 2px 10px rgba(0,0,0,0.15);
            max-width: 220px;
            font-size: 12px;
        ">
            <div style="font-weight:600;margin-bottom:8px;color:#000000;">
                Land cover clusters
            </div>
            {''.join(legend_items)}
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

    else:
        # Continuous choropleth
        # Folium Choropleth expects values; ensure column exists
        if layer not in gdf.columns:
            st.warning(f"Layer not found in GeoJSON: {layer}")
            return m

        folium.Choropleth(
            geo_data=gdf.to_json(),
            data=gdf[["h3_id", layer]],
            columns=["h3_id", layer],
            key_on="feature.properties.h3_id",
            fill_opacity=0.70,
            line_opacity=0.10,
            legend_name=LAYER_LABELS.get(layer, layer),
        ).add_to(m)
        
    return m


def main() -> None:
    st.set_page_config(
        page_title="Brazil Pantanal — Land Cover Clusters (H3 res 6)",
        layout="wide",
    )

    st.title("Brazil Pantanal — Land Cover Patterns (H3 res 6)")
    st.caption("H3 hexagon aggregation + WorldCover (10m) + WorldClim + KMeans clustering.")

    gdf = load_data()

    left, right = st.columns([1, 2], gap="large")

    with left:
        with st.expander("About this project", expanded=True):
            st.markdown(
                """
**Goal**  
Reveal land-cover patterns in the Brazilian Pantanal by aggregating raster datasets to an **H3 grid** (resolution 6)
and clustering hexagons based on land-cover composition.

**Data**  
- **ESA WorldCover 2021 (10m)** → land-cover proportions per hexagon  
- **WorldClim** → temperature (BIO1) and precipitation (BIO12)

**Method**  
1) Aggregate categorical land cover into proportions (wetland/tree/water/...)  
2) Merge with climate drivers  
3) Cluster hexagons using **KMeans** to detect dominant landscape types
"""
            )

        layer = st.selectbox(
            "Map layer",
            options=[
                "cluster_id",
                "p_wetland",
                "p_tree",
                "p_water",
                "p_shrub_grass",
                "p_cropland",
                "bio12_mean_mm",
                "bio1_mean_c",
            ],
            format_func=lambda x: LAYER_LABELS.get(x, x),
            index=0,
        )

        if "cluster_id" in gdf.columns:
            st.subheader("Cluster summary")
            summary = build_cluster_summary(gdf)
            if not summary.empty:
                st.dataframe(
                    summary,
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption("Values are mean proportions/climate per cluster + % of hexagons.")
            else:
                st.info("No cluster summary available.")
        else:
            st.info("cluster_id not found in the GeoJSON.")

    with right:
        m = make_map(gdf, layer)
        st_folium(m, use_container_width=True, height=720)


if __name__ == "__main__":
    main()
