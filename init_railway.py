"""Initialize Railway deployment: create tables and load data."""

import logging
import sys
from pathlib import Path

from holos_tools.core import Config, HolosDB
from holos_tools.load_centerlines import load_centerlines

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def init():
    """Initialize database with centerlines."""
    try:
        config = Config()
        db = HolosDB(config.db_url)

        # Check if tables already exist
        streets_exist = db.table_exists("street_centerlines")
        curbs_exist = db.table_exists("curb_centerlines")

        if streets_exist and curbs_exist:
            logger.info("✓ Tables already exist, skipping initialization")
            return

        logger.info("📍 Initializing Railway database...")

        docs_dir = Path(__file__).parent / "docs"

        if not streets_exist:
            logger.info("Loading street centerlines...")
            load_centerlines(
                docs_dir / "street_centerlines.geojson",
                "street_centerlines",
                schema="public",
            )

        if not curbs_exist:
            logger.info("Loading curb centerlines...")
            load_centerlines(
                docs_dir / "curb_centerlines.geojson",
                "curb_centerlines",
                schema="public",
            )

        logger.info("✓ Database initialized")
    except FileNotFoundError as e:
        logger.warning(
            f"GeoJSON files not found: {e}\n"
            "This is normal in production. Load data manually via load_centerlines.py"
        )
    except Exception as e:
        logger.error(f"Initialization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    init()
