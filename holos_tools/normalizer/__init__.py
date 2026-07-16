"""Normalizer: enforce master schema, reconcile categories, validate geography.

Phase 2 Step 1: Production hardening
- Classify Unknown categories via pattern matching
- Validate ward containment (ST_Contains check)
- Reconcile duplicates into conflation candidates
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import typer

app = typer.Typer(help="Normalizer: category reconciliation and geographic validation")


@dataclass
class NormalizationResult:
    """Result of normalizing a single record."""
    original_category: str
    inferred_category: str
    confidence: float
    reason: str
    requires_review: bool


# Category inference patterns (by location keywords)
CATEGORY_PATTERNS = {
    "Sidewalk": [r"sidewalk", r"sidealk", r"side walk"],
    "Street Resurfacing": [r"resurfacing", r"resurfac", r"pavement", r"street.*pave"],
    "Alley Resurfacing": [r"alley.*resurfac", r"alley.*pave"],
    "Alley Apron": [r"apron", r"alley.*apron"],
    "Curb & Gutter": [r"curb", r"gutter", r"curb.*gutter"],
    "Street Speed Hump": [r"speed hump", r"speed bump"],
    "Signs": [r"sign", r"signage"],
    "Alley Speed Hump": [r"alley.*speed", r"alley.*hump"],
    "Street Light": [r"street light", r"streetlight", r"light"],
    "Traffic Signal": [r"signal", r"traffic signal"],
    "Pedestrian": [r"pedestrian", r"countdown"],
    "Bollard": [r"bollard"],
    "Bike Lane": [r"bike lane", r"bike path"],
}


@app.command()
def classify_unknown(
    csv_path: str = typer.Option(
        "data/ward01_2017_menu_cleaned.csv",
        help="Path to cleaned CSV with Unknown categories"
    ),
    output_path: str = typer.Option(
        None,
        help="Output CSV path (auto-generate if not provided)"
    ),
):
    """Classify 'Unknown' categories via pattern matching on location text.

    Analyzes location strings to infer the most likely project category.
    Flags uncertain classifications for manual review.

    Example:
      holos normalizer classify-unknown --csv-path data/ward01_2017_menu_cleaned.csv
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

    typer.echo(f"🔍 Classifying Unknown categories in {len(records)} records...\n")

    classified = []
    unknown_count = 0
    classified_count = 0
    review_count = 0

    for idx, rec in enumerate(records, 1):
        category = rec.get('category', '').strip()
        location = rec.get('location', '').strip()

        if category == 'Unknown' or not category:
            unknown_count += 1
            result = _infer_category(location, category)

            rec['_inferred_category'] = result.inferred_category
            rec['_confidence'] = result.confidence
            rec['_reason'] = result.reason
            rec['_review'] = 'YES' if result.requires_review else 'NO'

            if result.confidence > 0.7:
                classified_count += 1
                status = "→"
            else:
                review_count += 1
                status = "?"

            typer.echo(
                f"  [{idx:4d}] {status} {location[:50]:<50} "
                f"→ {result.inferred_category} ({result.confidence:.0%})"
            )
        else:
            # Keep existing category
            rec['_inferred_category'] = category
            rec['_confidence'] = 1.0
            rec['_reason'] = 'existing'
            rec['_review'] = 'NO'

        classified.append(rec)

    # Output results
    if output_path is None:
        output_path = Path(csv_path).with_stem(
            Path(csv_path).stem + "_classified"
        )

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, 'w', newline='') as f:
        # Original fields + new classification fields
        fieldnames = [
            'ward', 'year', 'category', 'location', 'cost',
            '_inferred_category', '_confidence', '_reason', '_review'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(classified)

    # Summary
    typer.echo(f"\n✓ Classification complete")
    typer.echo(f"  Unknown entries: {unknown_count}")
    typer.echo(f"  High-confidence classifications: {classified_count}")
    typer.echo(f"  Require manual review: {review_count}")
    typer.echo(f"  Output: {out_file}")


def _infer_category(location: str, current_category: str) -> NormalizationResult:
    """Infer the most likely category from location text.

    Strategy:
    1. If current_category is known, return it (high confidence)
    2. If location matches category patterns, return matched category
    3. If location is ambiguous, return most likely with lower confidence
    4. Otherwise, escalate for human review
    """
    if current_category and current_category != 'Unknown':
        return NormalizationResult(
            original_category=current_category,
            inferred_category=current_category,
            confidence=1.0,
            reason="existing_category",
            requires_review=False
        )

    location_upper = location.upper()
    scores = {}

    # Score all categories by pattern matches
    for category, patterns in CATEGORY_PATTERNS.items():
        matches = sum(1 for p in patterns if re.search(p, location_upper, re.IGNORECASE))
        if matches > 0:
            scores[category] = matches

    if not scores:
        # No pattern matches; escalate
        return NormalizationResult(
            original_category=current_category or "Unknown",
            inferred_category="Unknown",
            confidence=0.0,
            reason="no_pattern_match",
            requires_review=True
        )

    # Return best match
    best_category = max(scores, key=scores.get)
    confidence = min(1.0, scores[best_category] / 3.0)  # Scale to 0-1

    return NormalizationResult(
        original_category=current_category or "Unknown",
        inferred_category=best_category,
        confidence=confidence,
        reason=f"pattern_match_{best_category}",
        requires_review=confidence < 0.7
    )


@app.command()
def validate_geography(
    geocoded_csv: str = typer.Option(
        "data/ward01_2017_menu_cleaned_geocoded.csv",
        help="Path to geocoded CSV"
    ),
):
    """Validate ward containment: geocoded points must be within assigned wards.

    Uses PostGIS ST_Contains to check if coordinates are actually within
    the ward they're assigned to. Flags mismatches for investigation.

    Example:
      holos normalizer validate-geography --geocoded-csv data/ward01_2017_menu_cleaned_geocoded.csv
    """
    csv_file = Path(geocoded_csv)
    if not csv_file.exists():
        typer.echo(f"✗ File not found: {geocoded_csv}", err=True)
        raise typer.Exit(1)

    try:
        import psycopg
    except ImportError:
        typer.echo("✗ psycopg3 required for geography validation", err=True)
        raise typer.Exit(1)

    # Connect to database (Supabase or local)
    import os
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    try:
        if supabase_url and supabase_key and supabase_key != "PASTE_SERVICE_ROLE_KEY_HERE":
            # Connect to Supabase
            # Supabase URL format: https://xxxxx.supabase.co
            # Extract project ref from URL
            project_ref = supabase_url.split("//")[1].split(".")[0]
            conn = psycopg.connect(
                host=f"{project_ref}.supabase.co",
                database="postgres",
                user="postgres",
                password=supabase_key,
                port=5432
            )
        else:
            # Fall back to local Postgres
            conn = psycopg.connect(
                dbname="holos",
                user="holos",
                host="127.0.0.1",
                port=5432,
                password="holos_dev_only"
            )
    except Exception as e:
        typer.echo(f"✗ Database connection failed: {e}", err=True)
        typer.echo(f"  Tip: Add SUPABASE_SERVICE_ROLE_KEY to .env to connect to production", err=True)
        raise typer.Exit(1)

    # Load geocoded CSV
    records = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        records = list(reader)

    typer.echo(f"📍 Validating ward containment for {len(records)} records...\n")

    passes = 0
    fails = 0
    skip = 0

    with conn.cursor() as cur:
        for idx, rec in enumerate(records, 1):
            ward = rec.get('ward', '').strip()
            lat = rec.get('_lat', '').strip()
            lon = rec.get('_lon', '').strip()

            if not (lat and lon and ward):
                skip += 1
                continue

            try:
                # Check if point is within ward polygon
                # Table: ref.wards (columns: ward_number, geom, vintage)
                cur.execute(
                    """
                    SELECT ST_Contains(
                        (SELECT geom FROM ref.wards
                         WHERE ward_number = %s
                         ORDER BY vintage DESC LIMIT 1),
                        ST_Point(%s, %s)
                    ) as is_contained
                    """,
                    (int(ward), float(lon), float(lat))
                )
                result = cur.fetchone()

                if result and result[0]:
                    passes += 1
                    status = "✓"
                else:
                    fails += 1
                    status = "✗"
                    typer.echo(
                        f"  [{idx:4d}] {status} Ward {ward} @ ({lat}, {lon}) "
                        f"— {rec.get('location', '')[:40]}"
                    )
            except Exception as e:
                skip += 1
                typer.echo(f"  [{idx:4d}] ? Error: {e}", err=True)

    conn.close()

    # Summary
    total_checked = passes + fails
    pass_rate = (passes / total_checked * 100) if total_checked > 0 else 0

    typer.echo(f"\n✓ Geography validation complete")
    typer.echo(f"  Passed (contained): {passes}/{total_checked} ({pass_rate:.1f}%)")
    typer.echo(f"  Failed (mismatch): {fails}/{total_checked}")
    typer.echo(f"  Skipped (missing coords): {skip}")
    typer.echo(f"  Note: Validation requires ref.wards table with ward_number + geom columns")

    if fails > 0:
        typer.echo(f"\n⚠️  {fails} records have ward-containment issues.")
        typer.echo(f"  These may indicate: (1) geocoding errors, (2) boundary changes,")
        typer.echo(f"  or (3) legitimate edge-case locations. See list above.")


if __name__ == "__main__":
    app()
