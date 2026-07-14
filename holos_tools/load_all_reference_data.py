"""Load all reference datasets into PostGIS."""

import logging
from pathlib import Path

from holos_tools.core import Config, HolosDB
from holos_tools.load_centerlines import load_centerlines

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def load_all_data():
    """Load all reference datasets into the database."""
    config = Config()
    db = HolosDB(config.db_url)
    docs_dir = Path(__file__).parent.parent / "docs"

    datasets = [
        # Centerlines (primary - high priority)
        ("street_centerlines.geojson", "street_centerlines", "Primary street centerlines for Chicago"),
        ("curb_centerlines.geojson", "curb_centerlines", "Curb centerlines for Chicago"),

        # Reference boundaries
        ("chicago_boundary.geojson", "chicago_boundary", "Chicago city boundary"),
        ("wards_2023.geojson", "wards_2023", "Chicago ward boundaries (2023)"),

        # Reference roads
        ("tiger_roads.geojson", "tiger_roads", "TIGER roads for Cook County"),

        # Aldermanic spending data (multi-year)
        ("2012_pages_2_20_verified.geojson", "aldermanic_2012", "2012 aldermanic spending"),
        ("2017_aldermanic_verified.geojson", "aldermanic_2017", "2017 aldermanic spending"),
        ("2025_menu_classified.geojson", "aldermanic_2025", "2025 aldermanic spending"),
    ]

    logger.info("📍 Loading reference datasets...")
    loaded = 0
    skipped = 0

    for filename, table_name, description in datasets:
        filepath = docs_dir / filename

        if not filepath.exists():
            logger.warning(f"⊘ {description}: file not found ({filename})")
            skipped += 1
            continue

        # Check if already loaded
        if db.table_exists(table_name):
            logger.info(f"✓ {description}: already exists, skipping")
            skipped += 1
            continue

        try:
            logger.info(f"📥 Loading {description} ({filepath.stat().st_size / 1024 / 1024:.1f}MB)...")
            load_centerlines(filepath, table_name, schema="public")
            logger.info(f"✓ {description}: loaded")
            loaded += 1
        except Exception as e:
            logger.error(f"✗ {description}: {e}")

    logger.info(f"✓ Data loading complete: {loaded} loaded, {skipped} skipped")


if __name__ == "__main__":
    load_all_data()
