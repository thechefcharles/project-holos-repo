"""Load street and curb centerlines into PostGIS."""

import logging
from pathlib import Path

import geopandas as gpd
from holos_tools.core import Config, HolosDB

logger = logging.getLogger(__name__)


def load_centerlines(geojson_path: Path, table_name: str, schema: str = "public") -> None:
    """Load GeoJSON centerlines to PostGIS table."""
    config = Config()
    db = HolosDB(config.db_url)

    logger.info(f"Loading {geojson_path} to {schema}.{table_name}...")

    # Read GeoJSON
    gdf = gpd.read_file(geojson_path)
    logger.info(f"Read {len(gdf)} features from {geojson_path.name}")

    # Ensure geometry column is named 'geom' for PostGIS
    if gdf.geometry.name != 'geom':
        gdf = gdf.rename_geometry('geom')

    # Load to PostGIS (replace if exists)
    db.load_geodataframe(gdf, table_name, schema=schema, if_exists='replace')
    logger.info(f"✓ Loaded to {schema}.{table_name}")


if __name__ == '__main__':
    import sys

    docs_dir = Path(__file__).parent.parent / 'docs'

    # Load street centerlines
    load_centerlines(
        docs_dir / 'street_centerlines.geojson',
        'street_centerlines',
        schema='public'
    )

    # Load curb centerlines
    load_centerlines(
        docs_dir / 'curb_centerlines.geojson',
        'curb_centerlines',
        schema='public'
    )

    logger.info("✓ All centerlines loaded to PostGIS")
