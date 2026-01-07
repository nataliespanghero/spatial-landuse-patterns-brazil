from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DB_PATH = PROJECT_ROOT / "data" / "database" / "analytics.duckdb"

HEX_PATH = DATA_PROCESSED / "h3_res6_cerrado.parquet"
ENV_PATH = DATA_PROCESSED / "features_worldclim.parquet"


def main() -> None:
    (PROJECT_ROOT / "data" / "database").mkdir(parents=True, exist_ok=True)

    if not HEX_PATH.exists():
        raise FileNotFoundError(f"Hex grid não encontrado: {HEX_PATH}")
    if not ENV_PATH.exists():
        raise FileNotFoundError(f"Features WorldClim não encontrado: {ENV_PATH}")

    hex_df = pd.read_parquet(HEX_PATH)[["h3_id"]].drop_duplicates()
    env_df = pd.read_parquet(ENV_PATH)

    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE OR REPLACE TABLE dim_hex AS SELECT * FROM hex_df")
    con.execute("CREATE OR REPLACE TABLE feat_env AS SELECT * FROM env_df")

    con.execute(
        """
        CREATE OR REPLACE VIEW feat_all AS
        SELECT
            h.h3_id,
            e.bio1_mean_c,
            e.bio12_mean_mm
        FROM dim_hex h
        LEFT JOIN feat_env e
        USING (h3_id)
        """
    )

    n_hex = con.execute("SELECT COUNT(*) FROM dim_hex").fetchone()[0]
    n_env = con.execute("SELECT COUNT(*) FROM feat_env").fetchone()[0]
    con.close()

    print("✅ DuckDB criado/atualizado.")
    print(f"   - DB: {DB_PATH}")
    print(f"   - dim_hex: {n_hex:,} linhas")
    print(f"   - feat_env: {n_env:,} linhas")


if __name__ == "__main__":
    main()
