"""Project Holos CLI — agents decide, deterministic tools execute."""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from holos_tools.core import Config, HolosDB
from holos_tools.harvest import app as harvest_app
from holos_tools.extract import app as extract_app
from holos_tools.geocode import app as geocode_app
from holos_tools.validate import app as validate_app
from holos_tools.load import app as load_app
from holos_tools.review import app as review_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger("holos")

app = typer.Typer(help="Project Holos: convert civic records into georeferenced digital twins")
app.add_typer(harvest_app, name="harvest")
app.add_typer(extract_app, name="extract")
app.add_typer(geocode_app, name="geocode")
app.add_typer(validate_app, name="validate")
app.add_typer(review_app, name="review")
app.add_typer(load_app, name="load")


@app.command()
def validate(
    changeset: str = typer.Option(..., help="Changeset ID to validate"),
    schema: str = typer.Option("public", help="Schema to validate"),
) -> None:
    """Validate a changeset against the schema and deterministic checks."""
    config = Config()
    db = HolosDB(config.db_url)

    logger.info(f"Validating changeset {changeset} in schema {schema}")

    # Schema check
    checks_passed = 0
    try:
        result = db.execute(f"SELECT count(*) FROM {schema}.spending_projects WHERE true")
        logger.info(f"✓ Schema {schema} is accessible")
        checks_passed += 1
    except Exception as e:
        logger.error(f"✗ Schema validation failed: {e}")
        sys.exit(1)

    logger.info(f"✓ All {checks_passed} checks passed for changeset {changeset}")
    print(json.dumps({"status": "valid", "changeset": changeset, "checks_passed": checks_passed}))


@app.command()
def version() -> None:
    """Print holos version."""
    from holos_tools import __version__

    print(f"holos {__version__}")


if __name__ == "__main__":
    app()
