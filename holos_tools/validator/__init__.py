"""Validator: manual accuracy review and correction of extracted spending records.

Phase 1 Step 2: Ward-specific data accuracy & extraction
- Load extracted CSV
- Identify records needing manual review
- Flag problematic entries (summary rows, missing categories, truncated locations)
- Support manual correction workflows
"""

import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
import typer

app = typer.Typer(help="Validator: review and correct extracted spending data")


@app.command()
def audit(
    csv_path: str = typer.Option(
        "data/ward01_2017_menu.csv",
        help="Path to CSV to audit"
    ),
    show_unknown: bool = typer.Option(
        True,
        help="Show all 'Unknown' category records"
    ),
    flag_summary_rows: bool = typer.Option(
        True,
        help="Flag likely summary/total rows"
    ),
):
    """Audit extracted CSV for data quality issues.

    Identifies:
    - Records with "Unknown" category (need manual categorization)
    - Summary/total rows (MENU BUDGET, WARD TOTAL, etc.)
    - Truncated locations (partial address due to PDF parsing)
    - Likely data quality issues
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        typer.echo(f"✗ File not found: {csv_path}", err=True)
        raise typer.Exit(1)

    records = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        records = list(reader)

    typer.echo(f"📊 Auditing {csv_file}")
    typer.echo(f"  Total records: {len(records)}\n")

    issues = {
        'unknown_category': [],
        'summary_rows': [],
        'truncated_location': [],
        'high_cost_round': [],
    }

    # Check each record
    for i, rec in enumerate(records):
        # Unknown category
        if show_unknown and rec['category'] == 'Unknown':
            issues['unknown_category'].append((i, rec))

        # Summary row detection
        if flag_summary_rows:
            location = rec['location'].upper()
            summary_keywords = ['MENU BUDGET', 'WARD TOTAL', 'BALANCE', 'COMMITTED']
            if any(kw in location for kw in summary_keywords):
                issues['summary_rows'].append((i, rec))

        # Truncated location (ends with & or partial street name)
        location = rec['location']
        if location.endswith('&') or location.endswith(','):
            issues['truncated_location'].append((i, rec))

        # Suspiciously round costs (likely summaries)
        try:
            cost = float(rec['cost'])
            if cost > 100000 and cost % 100000 == 0:
                issues['high_cost_round'].append((i, rec))
        except (ValueError, TypeError):
            pass

    # Print issues
    typer.echo("🚨 ISSUES FOUND:\n")

    if issues['unknown_category']:
        typer.echo(f"1. UNKNOWN CATEGORY ({len(issues['unknown_category'])} records)")
        typer.echo("   These need manual categorization:")
        for idx, rec in issues['unknown_category'][:10]:
            typer.echo(f"   Row {idx+2}: {rec['location'][:50]:<50} ${rec['cost']}")
        if len(issues['unknown_category']) > 10:
            typer.echo(f"   ... and {len(issues['unknown_category']) - 10} more")
        typer.echo()

    if issues['summary_rows']:
        typer.echo(f"2. SUMMARY/TOTAL ROWS ({len(issues['summary_rows'])} records)")
        typer.echo("   These should be filtered out (not projects):")
        for idx, rec in issues['summary_rows']:
            typer.echo(f"   Row {idx+2}: {rec['location'][:50]:<50} ${rec['cost']}")
        typer.echo()

    if issues['truncated_location']:
        typer.echo(f"3. TRUNCATED LOCATIONS ({len(issues['truncated_location'])} records)")
        typer.echo("   These may have PDF parsing errors:")
        for idx, rec in issues['truncated_location'][:5]:
            typer.echo(f"   Row {idx+2}: {rec['location'][:50]:<50}")
        if len(issues['truncated_location']) > 5:
            typer.echo(f"   ... and {len(issues['truncated_location']) - 5} more")
        typer.echo()

    if issues['high_cost_round']:
        typer.echo(f"4. SUSPICIOUSLY ROUND COSTS ({len(issues['high_cost_round'])} records)")
        typer.echo("   Likely summaries or budget allocations (may be legitimate):")
        for idx, rec in issues['high_cost_round'][:5]:
            typer.echo(f"   Row {idx+2}: {rec['location'][:50]:<50} ${rec['cost']}")
        typer.echo()

    # Summary statistics
    typer.echo("📈 Summary:")
    total_issues = sum(len(v) for v in issues.values())
    typer.echo(f"  Total issues flagged: {total_issues}")
    if total_issues == 0:
        typer.echo("  ✓ All checks passed!")


@app.command()
def clean(
    csv_path: str = typer.Option(
        "data/ward01_2017_menu.csv",
        help="Path to CSV to clean"
    ),
    output_path: str = typer.Option(
        None,
        help="Path to output cleaned CSV (auto-generate if not provided)"
    ),
):
    """Remove summary rows and obvious non-project entries.

    Filters out:
    - MENU BUDGET allocations
    - WARD TOTAL / BALANCE rows
    - Summary reporting (administrative entries)

    Keeps: All geographic projects for validation/geocoding
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        typer.echo(f"✗ File not found: {csv_path}", err=True)
        raise typer.Exit(1)

    if output_path is None:
        # Auto-generate output path
        output_path = csv_file.with_stem(csv_file.stem + "_cleaned")

    records = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        records = list(reader)

    # Filter: remove summary rows
    summary_keywords = ['MENU BUDGET', 'WARD TOTAL', 'BALANCE', 'WARD COMMITTED']
    cleaned = []
    for rec in records:
        location = rec['location'].upper()
        if not any(kw in location for kw in summary_keywords):
            cleaned.append(rec)

    # Write cleaned CSV
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, 'w', newline='') as f:
        fieldnames = records[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned)

    typer.echo(f"✓ Cleaned: {len(records)} → {len(cleaned)} records")
    typer.echo(f"  Removed: {len(records) - len(cleaned)} summary/administrative rows")
    typer.echo(f"  Output: {out_file}")


if __name__ == "__main__":
    app()
