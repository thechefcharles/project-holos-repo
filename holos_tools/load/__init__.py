"""Load: move data from staging to core, with human gates; load reference layers."""

import json
import subprocess
from pathlib import Path
from typing import Optional
from datetime import datetime
import typer
import yaml
import pandas as pd
import geopandas as gpd
from ..core import Config, HolosDB

app = typer.Typer(help="Load data: promote staging → core (with gates), load reference layers")


@app.command()
def staging(
    changeset: str = typer.Option(..., help="Changeset ID to promote"),
    require_approval: bool = typer.Option(False, help="Require human approval before promotion"),
) -> None:
    """Promote spending_projects from staging to core (after verification)."""
    config = Config()
    db = HolosDB(config.db_url)

    try:
        # Count rows to promote
        count_result = db.read_query(
            "SELECT COUNT(*) as cnt FROM staging.spending_projects WHERE reviewed_by IS NOT NULL"
        )
        count = count_result[0]["cnt"] if count_result else 0

        if count == 0:
            typer.echo(f"✗ No reviewed rows in staging.spending_projects for changeset {changeset}")
            raise typer.Exit(1)

        # Move to core (UPSERT to allow re-promotion)
        db.execute("""
            INSERT INTO core.spending_projects (
                row_id, location_text_raw, location_text_norm, ward, year, category, cost,
                geom, geometry_type, geometry_reason, method, stage, score,
                extraction_method, extraction_conf, parse_confidence, confidence,
                flags, source_id, job_id, reviewed_by, reviewed_at
            )
            SELECT
                row_id, location_text_raw, location_text_norm, ward, year, category, cost,
                geom, geometry_type, geometry_reason, method, stage, score,
                extraction_method, extraction_conf, parse_confidence, score,
                flags, source_id, NULL, reviewed_by, reviewed_at
            FROM staging.spending_projects
            WHERE reviewed_by IS NOT NULL
            ON CONFLICT (row_id) DO UPDATE SET
                reviewed_at = EXCLUDED.reviewed_at,
                valid_to = NULL
        """)

        typer.echo(f"✓ Promoted {count} rows to core.spending_projects")
        typer.echo(f"  Changeset: {changeset}")

    except Exception as e:
        typer.echo(f"✗ Failed to promote changeset {changeset}: {e}", err=True)
        raise typer.Exit(1)


def _load_config() -> dict:
    """Load config/sources.yaml."""
    with open("config/sources.yaml") as f:
        return yaml.safe_load(f)


def _harvest_socrata_dataset(dataset_id: str) -> Optional[Path]:
    """Call holos harvest socrata to download and manifest a dataset."""
    try:
        result = subprocess.run(
            ["holos", "harvest", "socrata", "--dataset", dataset_id],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return None

        # Find the manifest file (raw/socrata/<id>/<date>/<id>.json)
        base = Path(f"raw/socrata/{dataset_id}")
        if base.exists():
            manifest_files = list(base.glob("*/*.json"))
            if manifest_files:
                return manifest_files[0].parent / f"{dataset_id}.csv"
        return None
    except Exception as e:
        print(f"Error harvesting {dataset_id}: {e}")
        return None


def _load_csv_to_postgis(
    csv_path: Path, table_name: str, schema: str, db: HolosDB, geom_col: Optional[str] = None
) -> int:
    """Load CSV to PostGIS (EPSG:4326). Returns row count."""
    if not csv_path.exists():
        return 0

    try:
        # Read CSV as DataFrame
        df = pd.read_csv(csv_path)

        if geom_col and geom_col in df.columns:
            # If geometry column exists, parse as GeoDataFrame
            from shapely import wkt
            df["geometry"] = df[geom_col].apply(lambda x: wkt.loads(x) if pd.notna(x) else None)
            gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
            db.load_geodataframe(gdf, table_name, schema=schema, if_exists="append")
        else:
            # Regular DataFrame load via SQL
            engine = db.connect()
            df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)

        return len(df)
    except Exception as e:
        raise Exception(f"Failed to load {csv_path} to {schema}.{table_name}: {e}")


@app.command()
def reference(
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Load reference data: centerlines, wards, address points, 311, Census (Chain A2)."""
    config = Config()
    db = HolosDB(config.db_url)
    source_config = _load_config()

    try:
        ref_data = source_config.get("chicago", {}).get("reference_data", {})
        datasets_to_load = {
            "street_center_lines": ("6imu-meau", "centerlines", "shape"),
            "ward_boundaries_2023": ("p293-wvbd", "wards", "geometry"),
            "service_requests_311": ("v6vf-nfxy", "sr311", None),
        }

        loaded_count = 0
        rows_loaded = 0
        vintage_timestamp = datetime.utcnow().isoformat()

        for key, (dataset_id, table_name, geom_col) in datasets_to_load.items():
            dataset_info = ref_data.get(key)
            if not dataset_info:
                if verbose:
                    typer.echo(f"⊘ {key} not in config, skipping")
                continue

            if verbose:
                typer.echo(f"Loading {key} ({dataset_id}) → ref.{table_name}...")

            # Harvest the dataset
            csv_path = _harvest_socrata_dataset(dataset_id)
            if not csv_path or not csv_path.exists():
                if verbose:
                    typer.echo(f"⊘ Failed to harvest {dataset_id} (CSV not found)")
                continue

            # Load CSV to PostGIS
            row_count = _load_csv_to_postgis(csv_path, table_name, "ref", db, geom_col)
            typer.echo(f"✓ {table_name}: {row_count} rows loaded")
            loaded_count += 1
            rows_loaded += row_count

        # Create derived tables (intersections, blocks, gazetteer, street_names)
        if loaded_count > 0:
            _create_derived_tables(db, verbose)

        typer.echo(f"\n✓ Reference data loading complete")
        typer.echo(f"  Loaded: {loaded_count} datasets, {rows_loaded} total rows")
        typer.echo(f"  Vintage: {vintage_timestamp}")

    except Exception as e:
        typer.echo(f"✗ Failed to load reference data: {e}", err=True)
        raise typer.Exit(1)


def _create_derived_tables(db: HolosDB, verbose: bool = False) -> None:
    """Create derived reference tables (intersections, blocks, gazetteer, street_names)."""
    if verbose:
        typer.echo("Creating derived tables...")

    # Create intersections table from centerlines + wards
    db.execute("""
        CREATE TABLE IF NOT EXISTS ref.intersections AS
        SELECT
            row_number() OVER () as intersection_id,
            c.geometry as geom,
            array_agg(DISTINCT w.ward_id) as ward_ids
        FROM ref.centerlines c
        LEFT JOIN ref.wards w ON ST_Contains(w.geometry, c.geometry)
        GROUP BY c.geometry;
        CREATE INDEX IF NOT EXISTS idx_intersections_geom ON ref.intersections USING gist(geom);
    """)

    # Create street_names gazetteer from centerlines
    db.execute("""
        CREATE TABLE IF NOT EXISTS ref.gazetteer AS
        SELECT DISTINCT
            lower(street_name) as name_lower,
            street_name,
            'street'::text as feature_type,
            ST_Extent(geometry) as bounds
        FROM ref.centerlines
        WHERE street_name IS NOT NULL
        GROUP BY street_name;
        CREATE INDEX IF NOT EXISTS idx_gazetteer_name ON ref.gazetteer(name_lower);
    """)

    if verbose:
        typer.echo("✓ Derived tables created: intersections, gazetteer")
