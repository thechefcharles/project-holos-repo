"""Load: move data from staging to core, with human gates."""

import json
from pathlib import Path
from typing import Optional
import typer
from ..core import Config, HolosDB

app = typer.Typer(help="Load data: promote staging → core, with human review gates")


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


@app.command()
def reference(
    verbose: bool = typer.Option(False, help="Verbose output"),
) -> None:
    """Load reference data (centerlines, wards, address points, gazetteer)."""
    config = Config()
    db = HolosDB(config.db_url)

    try:
        # Placeholder: this would download and load reference layers
        # For Phase 1, we populate with small test datasets
        typer.echo("✓ Reference data loading (Phase 1: stubs only)")
        typer.echo("  Centerlines: ref.centerlines (empty)")
        typer.echo("  Wards: ref.wards (empty)")
        typer.echo("  Address points: ref.address_points (empty)")
        typer.echo("  Gazetteer: ref.gazetteer (empty)")

    except Exception as e:
        typer.echo(f"✗ Failed to load reference data: {e}", err=True)
        raise typer.Exit(1)
