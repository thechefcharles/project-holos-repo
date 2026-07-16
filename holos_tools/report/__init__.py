"""Report Cards: Spending analysis by ward, category, and geography.

Phase 2 Option C: Production analytics
- Aggregate spending by ward, category, year
- Cost-per-unit metrics (per street mile, per alley segment, etc.)
- Geographic heat maps (spend concentration)
- Year-over-year trends
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
import typer

app = typer.Typer(help="Report Cards: spending analysis and dashboards")


@app.command()
def by_ward(
    year: int = typer.Option(2017, help="Year to analyze"),
    geocoded_only: bool = typer.Option(True, help="Only include geocoded records"),
):
    """Generate spending report by ward.

    Shows total spend, project count, and geocoding success rate per ward.

    Example:
      holos report by-ward --year 2017
    """
    base_path = Path("data")

    ward_stats = {}

    # Aggregate all wards
    for ward in range(1, 51):
        geocoded_file = base_path / f"ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"

        if not geocoded_file.exists():
            continue

        with open(geocoded_file, 'r') as f:
            reader = csv.DictReader(f)
            total_spend = 0.0
            total_records = 0
            geocoded_count = 0
            geocoded_spend = 0.0

            for row in reader:
                total_records += 1
                cost = float(row.get('cost', 0))
                total_spend += cost

                has_coords = row.get('_lat', '').strip()
                if has_coords:
                    geocoded_count += 1
                    geocoded_spend += cost

        if total_records > 0:
            geocode_rate = geocoded_count / total_records * 100
            spend_rate = geocoded_spend / total_spend * 100 if total_spend > 0 else 0

            ward_stats[ward] = {
                "projects": total_records,
                "spend": f"${total_spend:,.2f}",
                "geocoded_projects": geocoded_count,
                "geocoded_spend": f"${geocoded_spend:,.2f}",
                "geocode_rate_by_count": f"{geocode_rate:.1f}%",
                "geocode_rate_by_spend": f"{spend_rate:.1f}%",
            }

    # Output report
    typer.echo(f"\n📊 WARD SPENDING REPORT — {year}\n")
    typer.echo(f"{'Ward':<6} {'Projects':<10} {'Spend':<15} {'Geocoded %':<12} {'Spend %':<12}")
    typer.echo("=" * 60)

    total_projects = 0
    total_spend = 0.0
    total_geocoded = 0
    total_geocoded_spend = 0.0

    for ward in sorted(ward_stats.keys()):
        stats = ward_stats[ward]
        projects = int(stats['projects'])
        geocoded = int(stats['geocoded_projects'])
        geocode_pct = float(stats['geocode_rate_by_count'].rstrip('%'))

        total_projects += projects
        total_geocoded += geocoded

        typer.echo(
            f"{ward:<6} {projects:<10} {stats['spend']:<15} "
            f"{geocode_pct:.1f}%{'':<8} {stats['geocode_rate_by_spend']:<12}"
        )

    typer.echo("=" * 60)
    overall_rate = (total_geocoded / total_projects * 100) if total_projects > 0 else 0
    typer.echo(f"{'TOTAL':<6} {total_projects:<10} {'':15} {overall_rate:.1f}%")

    # Save detailed report
    report_file = Path("data") / f"report_by_ward_{year}.json"
    with open(report_file, 'w') as f:
        json.dump({"year": year, "wards": ward_stats}, f, indent=2)

    typer.echo(f"\n✓ Detailed report: {report_file}")


@app.command()
def by_category(
    year: int = typer.Option(2017, help="Year to analyze"),
):
    """Generate spending report by category.

    Shows total spend and project count per category across all wards.

    Example:
      holos report by-category --year 2017
    """
    base_path = Path("data")

    category_stats = defaultdict(lambda: {"count": 0, "spend": 0.0, "geocoded": 0})

    # Aggregate all wards
    for ward in range(1, 51):
        cleaned_file = base_path / f"ward{ward:02d}_{year}_menu_cleaned.csv"

        if not cleaned_file.exists():
            continue

        with open(cleaned_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                category = row.get('category', 'Unknown').strip()
                cost = float(row.get('cost', 0))

                category_stats[category]["count"] += 1
                category_stats[category]["spend"] += cost

    # Load geocoding data to count geocoded by category
    for ward in range(1, 51):
        geocoded_file = base_path / f"ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"
        if not geocoded_file.exists():
            continue

        with open(geocoded_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                category = row.get('category', 'Unknown').strip()
                if row.get('_lat', '').strip():
                    category_stats[category]["geocoded"] += 1

    # Output report
    typer.echo(f"\n📊 CATEGORY SPENDING REPORT — {year}\n")
    typer.echo(f"{'Category':<30} {'Projects':<10} {'Spend':<15} {'Geocoded':<10}")
    typer.echo("=" * 70)

    sorted_cats = sorted(category_stats.items(), key=lambda x: x[1]["spend"], reverse=True)

    for category, stats in sorted_cats:
        category_display = category[:28]
        spend_str = f"${stats['spend']:,.0f}"
        typer.echo(
            f"{category_display:<30} {stats['count']:<10} "
            f"{spend_str:<15} {stats['geocoded']:<10}"
        )

    typer.echo("=" * 70)
    total_spend = sum(s["spend"] for s in category_stats.values())
    total_projects = sum(s["count"] for s in category_stats.values())
    typer.echo(f"{'TOTAL':<30} {total_projects:<10} ${total_spend:,.0f}")

    # Save detailed report
    report_file = Path("data") / f"report_by_category_{year}.json"
    with open(report_file, 'w') as f:
        json.dump(
            {
                "year": year,
                "categories": {
                    cat: {
                        "count": stats["count"],
                        "spend": f"${stats['spend']:,.2f}",
                        "geocoded": stats["geocoded"],
                    }
                    for cat, stats in sorted_cats
                }
            },
            f,
            indent=2
        )

    typer.echo(f"\n✓ Detailed report: {report_file}")


@app.command()
def summary(
    year: int = typer.Option(2017, help="Year to analyze"),
):
    """Generate executive summary of spending for a year.

    Shows key metrics: total spend, geocoding rate, top categories, top wards.

    Example:
      holos report summary --year 2017
    """
    base_path = Path("data")

    total_projects = 0
    total_spend = 0.0
    geocoded_projects = 0
    geocoded_spend = 0.0

    categories = defaultdict(float)
    wards = defaultdict(lambda: {"spend": 0.0, "count": 0})

    # First pass: aggregate all data
    for ward in range(1, 51):
        cleaned_file = base_path / f"ward{ward:02d}_{year}_menu_cleaned.csv"
        if not cleaned_file.exists():
            continue

        with open(cleaned_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_projects += 1
                cost = float(row.get('cost', 0))
                total_spend += cost

                category = row.get('category', 'Unknown')
                categories[category] += cost

                wards[ward]["spend"] += cost
                wards[ward]["count"] += 1

    # Second pass: count geocoded
    for ward in range(1, 51):
        geocoded_file = base_path / f"ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"
        if not geocoded_file.exists():
            continue

        with open(geocoded_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('_lat', '').strip():
                    geocoded_projects += 1
                    geocoded_spend += float(row.get('cost', 0))

    # Generate report
    typer.echo(f"\n" + "=" * 60)
    typer.echo(f"PROJECT HOLOS — EXECUTIVE SUMMARY ({year})")
    typer.echo("=" * 60 + "\n")

    geocode_rate_count = (geocoded_projects / total_projects * 100) if total_projects else 0
    geocode_rate_spend = (geocoded_spend / total_spend * 100) if total_spend else 0

    typer.echo(f"Total Spending: ${total_spend:,.0f}")
    typer.echo(f"Total Projects: {total_projects}")
    typer.echo(f"Geocoding Success Rate: {geocode_rate_count:.1f}% by count, {geocode_rate_spend:.1f}% by spend")
    typer.echo(f"Geolocated Spend: ${geocoded_spend:,.0f}\n")

    # Top categories
    typer.echo("Top 5 Categories by Spend:")
    top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]
    for i, (cat, spend) in enumerate(top_cats, 1):
        pct = (spend / total_spend * 100) if total_spend else 0
        typer.echo(f"  {i}. {cat}: ${spend:,.0f} ({pct:.1f}%)")

    typer.echo(f"\nTop 5 Wards by Spend:")
    top_wards = sorted(wards.items(), key=lambda x: x[1]["spend"], reverse=True)[:5]
    for i, (ward, stats) in enumerate(top_wards, 1):
        pct = (stats["spend"] / total_spend * 100) if total_spend else 0
        typer.echo(f"  {i}. Ward {ward}: ${stats['spend']:,.0f} ({pct:.1f}%)")

    typer.echo("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    app()
