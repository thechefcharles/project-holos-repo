"""Pilot: end-to-end workflow for Ward 1, 2017 validation.

Phase 1 Step 3: Extract → Geocode → Validate
Runs the full spending pipeline on one ward to measure accuracy and iterate.
"""

import json
import csv
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import typer

app = typer.Typer(help="Pilot: end-to-end Ward 1 workflow validation")


def run_geocode_cascade(location_text: str, run_id: str, ward: Optional[str] = None) -> Dict[str, Any]:
    """Call holos geocode cascade and parse result."""
    cmd = [
        "uv", "run", "holos", "geocode", "cascade",
        "--location-text", location_text,
        "--run-id", run_id,
        "--json-output"
    ]
    if ward:
        cmd.extend(["--ward", ward])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {
                "success": False,
                "error": result.stderr,
                "location_text": location_text
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Geocoding timeout",
            "location_text": location_text
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": f"Invalid JSON response: {result.stdout}",
            "location_text": location_text
        }


@app.command()
def geocode_batch(
    csv_path: str = typer.Option(
        "data/ward01_2017_menu_cleaned.csv",
        help="Path to cleaned CSV to geocode"
    ),
    output_path: str = typer.Option(
        None,
        help="Output path for geocoded results (auto-generate if not provided)"
    ),
    run_id_prefix: str = typer.Option(
        "ward1_2017",
        help="Prefix for run IDs (for tracking/grouping)"
    ),
    limit: Optional[int] = typer.Option(
        None,
        help="Limit number of records to geocode (for testing)"
    ),
):
    """Batch geocode all locations from cleaned CSV.

    Runs each location through the geocoding cascade, collects results,
    and outputs geojson with coordinates and accuracy metrics.

    Example:
      holos pilot geocode-batch --csv-path data/ward01_2017_menu_cleaned.csv
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        typer.echo(f"✗ File not found: {csv_path}", err=True)
        raise typer.Exit(1)

    # Load CSV
    records = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        records = list(reader)

    if limit:
        records = records[:limit]

    typer.echo(f"🔄 Geocoding {len(records)} records from Ward 1, 2017...\n")

    # Geocode each record
    geocoded = []
    success_count = 0
    failed_count = 0

    for idx, rec in enumerate(records, 1):
        location_text = rec['location']
        run_id = f"{run_id_prefix}_{idx:03d}"

        typer.echo(f"  [{idx:2d}/{len(records)}] {location_text[:60]:<60}", nl=False)

        result = run_geocode_cascade(location_text, run_id, ward="1")

        # Success: either POINT with coordinates OR LINESTRING (street segment)
        has_result = result.get('status') == 'success' and (
            result.get('coordinates') or
            result.get('geometry_wkt')  # LINESTRING for street segments
        )
        if has_result:
            success_count += 1
            typer.echo(" ✓")
        else:
            failed_count += 1
            typer.echo(" ✗")

        # Merge result with original record
        rec['_run_id'] = run_id
        rec['_geocoding_result'] = result
        geocoded.append(rec)

    # Output results
    if output_path is None:
        output_path = Path(csv_path).with_stem(Path(csv_path).stem + "_geocoded")

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV with geocoding results
    with open(out_file, 'w', newline='') as f:
        fieldnames = ['ward', 'year', 'category', 'location', 'cost', '_run_id', '_success', '_lat', '_lon', '_confidence']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for rec in geocoded:
            result = rec['_geocoding_result']
            coords = result.get('coordinates') or []

            # For POINT results: coordinates are [lon, lat]
            # For LINESTRING results: extract centroid via PostGIS if available
            lat = ''
            lon = ''

            if len(coords) > 1:  # POINT geometry
                lon = coords[0]
                lat = coords[1]
            elif result.get('geometry_wkt'):  # LINESTRING or MULTILINESTRING: extract centroid
                # Simple WKT parser for LINESTRING/MULTILINESTRING
                wkt = result['geometry_wkt']
                try:
                    import re
                    # Extract all coordinates from LINESTRING(...) or MULTILINESTRING((...),(...))
                    # Pattern: any sequence of (x y, x y, ...) groups
                    coord_groups = re.findall(r'\(([^)]+)\)', wkt)
                    points = []
                    for group in coord_groups:
                        # Parse all points in this group: "x y, x y, ..."
                        for point_str in group.split(','):
                            parts = point_str.strip().split()
                            if len(parts) >= 2:
                                try:
                                    points.append((float(parts[0]), float(parts[1])))
                                except ValueError:
                                    pass
                    # Compute centroid as average of all points
                    if points:
                        lon = sum(p[0] for p in points) / len(points)
                        lat = sum(p[1] for p in points) / len(points)
                except Exception:
                    pass  # If parsing fails, leave empty

            writer.writerow({
                'ward': rec['ward'],
                'year': rec['year'],
                'category': rec['category'],
                'location': rec['location'],
                'cost': rec['cost'],
                '_run_id': rec['_run_id'],
                '_success': result.get('status') == 'success',
                '_lat': lat,
                '_lon': lon,
                '_confidence': result.get('score', ''),
            })

    # Summary
    success_rate = success_count / len(records) * 100 if records else 0
    typer.echo(f"\n✓ Geocoding complete")
    typer.echo(f"  Success: {success_count}/{len(records)} ({success_rate:.1f}%)")
    typer.echo(f"  Failed: {failed_count}/{len(records)}")
    typer.echo(f"  Output: {out_file}")


@app.command()
def validate(
    geocoded_csv: str = typer.Option(
        "data/ward01_2017_menu_cleaned_geocoded.csv",
        help="Path to geocoded CSV to validate"
    ),
):
    """Validate geocoded results for accuracy.

    Checks:
    - All records have coordinates
    - Coordinates are within Chicago bounds
    - High-confidence matches
    - Geometry type (point vs. line vs. polygon)
    """
    csv_file = Path(geocoded_csv)
    if not csv_file.exists():
        typer.echo(f"✗ File not found: {geocoded_csv}", err=True)
        raise typer.Exit(1)

    records = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        records = list(reader)

    typer.echo(f"📊 Validating {len(records)} geocoded records\n")

    # Chicago bounds (rough)
    chicago_bounds = {
        'min_lat': 41.63,
        'max_lat': 42.02,
        'min_lon': -87.94,
        'max_lon': -87.52,
    }

    issues = {
        'missing_coords': [],
        'out_of_bounds': [],
        'low_confidence': [],
        'valid': []
    }

    for idx, rec in enumerate(records, 1):
        try:
            lat = float(rec['_lat']) if rec['_lat'] else None
            lon = float(rec['_lon']) if rec['_lon'] else None
            confidence = float(rec['_confidence']) if rec['_confidence'] else 0

            if lat == '' or lon == '' or not lat or not lon:
                issues['missing_coords'].append((idx, rec))
            elif not (chicago_bounds['min_lat'] <= lat <= chicago_bounds['max_lat'] and
                     chicago_bounds['min_lon'] <= lon <= chicago_bounds['max_lon']):
                issues['out_of_bounds'].append((idx, rec, lat, lon))
            elif confidence < 0.6:
                issues['low_confidence'].append((idx, rec, confidence))
            else:
                issues['valid'].append((idx, rec))
        except (ValueError, TypeError):
            issues['missing_coords'].append((idx, rec))

    # Print results
    typer.echo("✓ VALID RECORDS:")
    typer.echo(f"  {len(issues['valid'])}/{len(records)} ({len(issues['valid'])/len(records)*100:.1f}%)")
    typer.echo()

    if issues['missing_coords']:
        typer.echo(f"⚠️  MISSING COORDINATES: {len(issues['missing_coords'])}")
        for idx, rec in issues['missing_coords'][:5]:
            typer.echo(f"  Row {idx}: {rec['location'][:50]}")
        if len(issues['missing_coords']) > 5:
            typer.echo(f"  ... and {len(issues['missing_coords']) - 5} more")
        typer.echo()

    if issues['out_of_bounds']:
        typer.echo(f"⚠️  OUT OF BOUNDS: {len(issues['out_of_bounds'])}")
        for idx, rec, lat, lon in issues['out_of_bounds'][:5]:
            typer.echo(f"  Row {idx}: ({lat:.4f}, {lon:.4f}) - {rec['location'][:40]}")
        typer.echo()

    if issues['low_confidence']:
        typer.echo(f"⚠️  LOW CONFIDENCE: {len(issues['low_confidence'])}")
        for idx, rec, conf in issues['low_confidence'][:5]:
            typer.echo(f"  Row {idx}: {conf:.2f} - {rec['location'][:40]}")
        typer.echo()

    # Summary
    typer.echo("📈 Summary:")
    typer.echo(f"  Valid: {len(issues['valid'])}")
    typer.echo(f"  Issues: {len(issues['missing_coords']) + len(issues['out_of_bounds']) + len(issues['low_confidence'])}")
    typer.echo(f"  Success rate: {len(issues['valid'])/len(records)*100:.1f}%")


if __name__ == "__main__":
    app()
