"""Initialize Railway deployment: create tables and load data."""

import logging
import sys
import time
from pathlib import Path

from holos_tools.core import Config, HolosDB
from holos_tools.load_centerlines import load_centerlines

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def wait_for_database(max_retries: int = 60, delay: int = 2) -> HolosDB:
    """Wait for database to be ready, with exponential backoff."""
    config = Config()
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting database connection ({attempt + 1}/{max_retries})...")
            db = HolosDB(config.db_url)
            db.execute("SELECT 1")  # Test query
            logger.info("✓ Database is ready")
            return db
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = delay * (attempt // 10 + 1)  # Slow backoff
                logger.warning(f"Database not ready: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Database failed to connect after {max_retries} attempts")
                raise


def init():
    """Initialize database with centerlines."""
    try:
        logger.info("🚀 Starting Railway initialization...")
        db = wait_for_database()

        # Check if tables already exist
        streets_exist = db.table_exists("street_centerlines")
        curbs_exist = db.table_exists("curb_centerlines")

        if streets_exist and curbs_exist:
            logger.info("✓ Tables already exist, skipping initialization")
            return

        logger.info("📍 Loading centerline data...")
        docs_dir = Path(__file__).parent / "docs"

        if not streets_exist:
            logger.info("Loading street centerlines (56k features)...")
            load_centerlines(
                docs_dir / "street_centerlines.geojson",
                "street_centerlines",
                schema="public",
            )
            logger.info("✓ Street centerlines loaded")

        if not curbs_exist:
            logger.info("Loading curb centerlines (169k features)...")
            load_centerlines(
                docs_dir / "curb_centerlines.geojson",
                "curb_centerlines",
                schema="public",
            )
            logger.info("✓ Curb centerlines loaded")

        logger.info("✓ Database initialization complete")
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
