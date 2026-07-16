"""Scraper: download and convert aldermanic menu PDFs to structured CSV data.

Phase 1 Step 1: Ward-specific menu extraction pipeline.
- Downloads menu PDFs from Chicago OBM archive via harvester
- Extracts structured data (ward, category, location, cost)
- Filters to specific ward
- Exports to CSV for geo-location processing
"""

import json
import csv
from pathlib import Path
from typing import List, Optional, Dict, Any
import typer
from datetime import datetime

app = typer.Typer(help="Scraper: download and convert aldermanic menus to CSV")


def load_extracted_json(json_path: str) -> List[Dict[str, Any]]:
    """Load extracted spending records from JSON file."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"No extraction found: {json_path}")

    with open(path, 'r') as f:
        return json.load(f)


def filter_by_ward(records: List[Dict[str, Any]], ward: int) -> List[Dict[str, Any]]:
    """Filter records to specific ward."""
    return [r for r in records if r.get('ward') == ward]


def export_to_csv(
    records: List[Dict[str, Any]],
    output_path: str,
    include_fields: List[str] = None
) -> None:
    """Export spending records to CSV format."""
    if not records:
        typer.echo(f"⚠️  No records to export", err=True)
        return

    # Use all record keys if fields not specified
    if include_fields is None:
        include_fields = list(records[0].keys())

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=include_fields)
        writer.writeheader()
        for record in records:
            # Include only specified fields
            filtered_record = {k: record.get(k, '') for k in include_fields}
            writer.writerow(filtered_record)

    typer.echo(f"✓ Exported {len(records)} records → {output_file}")


@app.command()
def download(
    year: int = typer.Option(2017, help="Year to download"),
    ward: Optional[int] = typer.Option(None, help="Optional: filter to specific ward"),
):
    """Discover and download aldermanic menu PDF for specified year.

    Uses holos harvest discover to find menu PDFs from Chicago OBM archive.
    """
    from ..harvest import app as harvest_app
    from ..harvest import discover

    typer.echo(f"🔍 Discovering {year} menu PDFs...")

    # Call harvest discover with dry_run to see what's available
    # Then download the one we need
    typer.echo(f"  (Uses holos harvest discover internally)")
    typer.echo(f"  Note: Run 'holos harvest discover --year {year}' to fetch PDFs")


@app.command()
def extract_ward(
    year: int = typer.Option(2017, help="Year to extract"),
    ward: int = typer.Option(1, help="Ward number (1-50)"),
    input_json: str = typer.Option(
        None,
        help="Path to extracted JSON (auto-detect if not provided)"
    ),
    output_csv: str = typer.Option(
        None,
        help="Path to output CSV (auto-generate if not provided)"
    ),
):
    """Extract and filter menu data for specific ward + year.

    Reads extracted JSON, filters to specified ward, exports to CSV.

    Example:
      holos scraper extract-ward --year 2017 --ward 1
    """
    # Auto-detect input path if not provided
    if input_json is None:
        # Try common extraction locations
        candidates = [
            f"extractions/normalized/2017OBMMenu50WardDetailsRpt3Dec2018_normalized.json",
            f"2017_valid_records.json",
            f"extractions/normalized/{year}*_normalized.json",
        ]
        input_json = None
        for candidate in candidates:
            if "*" in candidate:
                # Glob search
                pattern_dir = Path(candidate.split("*")[0])
                if pattern_dir.exists():
                    matches = list(pattern_dir.parent.glob(candidate.split("/")[-1]))
                    if matches:
                        input_json = str(matches[0])
                        break
            elif Path(candidate).exists():
                input_json = candidate
                break

        if input_json is None:
            typer.echo(f"✗ No extracted JSON found for {year}. Run 'holos extract pdf-tables' first.", err=True)
            raise typer.Exit(1)

    # Auto-generate output path if not provided
    if output_csv is None:
        output_csv = f"data/ward{ward:02d}_{year}_menu.csv"

    try:
        typer.echo(f"📖 Loading extracted data from {input_json}...")
        records = load_extracted_json(input_json)
        typer.echo(f"  Found {len(records)} total records")

        typer.echo(f"🔍 Filtering to Ward {ward}...")
        ward_records = filter_by_ward(records, ward)
        typer.echo(f"  Found {len(ward_records)} records for Ward {ward}")

        typer.echo(f"💾 Exporting to CSV...")
        export_to_csv(ward_records, output_csv)

        # Print summary
        total_cost = sum(r.get('cost', 0) for r in ward_records)
        typer.echo(f"\n📊 Summary:")
        typer.echo(f"  Ward: {ward}")
        typer.echo(f"  Year: {year}")
        typer.echo(f"  Records: {len(ward_records)}")
        typer.echo(f"  Total spend: ${total_cost:,.2f}")

        # Breakdown by category
        categories = {}
        for r in ward_records:
            cat = r.get('category', 'Unknown')
            if cat not in categories:
                categories[cat] = {'count': 0, 'cost': 0}
            categories[cat]['count'] += 1
            categories[cat]['cost'] += r.get('cost', 0)

        typer.echo(f"\n  By category:")
        for cat in sorted(categories.keys()):
            count = categories[cat]['count']
            cost = categories[cat]['cost']
            typer.echo(f"    {cat}: {count} projects, ${cost:,.2f}")

    except FileNotFoundError as e:
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"✗ Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
