"""Workflow: orchestrate the full pipeline for multi-ward, multi-year processing.

Phase 1 Step 7: Workflow expansion orchestration
- Parameterize pipeline for any ward and year
- Run full extract → geocode → measure → segment for multiple wards
- Track results and success rates
- Enable multi-year analysis
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import typer
import subprocess

app = typer.Typer(help="Workflow: orchestrate full pipeline across wards and years")


def run_pipeline_for_ward(ward: int, year: int, force: bool = False) -> Dict[str, Any]:
    """Run the full pipeline for a given ward and year.

    Returns:
        Pipeline result dictionary with status and metrics
    """
    result = {
        'ward': ward,
        'year': year,
        'timestamp': datetime.now().isoformat(),
        'steps': {}
    }

    # Step 1: Extract (scraper)
    typer.echo(f"\n[Ward {ward}, {year}] Step 1: Extract...")
    csv_path = f"data/ward{ward:02d}_{year}_menu.csv"

    if Path(csv_path).exists() and not force:
        typer.echo(f"  ✓ Already extracted")
        result['steps']['extract'] = 'skipped'
    else:
        try:
            cmd = ["uv", "run", "holos", "scraper", "extract-ward", "--year", str(year), "--ward", str(ward)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            result['steps']['extract'] = 'success'
            typer.echo(f"  ✓ Extracted")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            result['steps']['extract'] = f'failed: {str(e)}'
            typer.echo(f"  ✗ Failed: {e}")
            return result

    # Step 2: Validate & Clean
    typer.echo(f"[Ward {ward}, {year}] Step 2: Validate...")
    cleaned_path = f"data/ward{ward:02d}_{year}_menu_cleaned.csv"

    if Path(cleaned_path).exists() and not force:
        typer.echo(f"  ✓ Already cleaned")
        result['steps']['validate'] = 'skipped'
    else:
        try:
            cmd = ["uv", "run", "holos", "validator", "clean", "--csv-path", csv_path]
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            result['steps']['validate'] = 'success'
            typer.echo(f"  ✓ Validated and cleaned")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            result['steps']['validate'] = f'failed: {str(e)}'
            typer.echo(f"  ✗ Failed: {e}")
            return result

    # Step 3: Geocode
    typer.echo(f"[Ward {ward}, {year}] Step 3: Geocode...")
    geocoded_path = f"data/ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"

    if Path(geocoded_path).exists() and not force:
        typer.echo(f"  ✓ Already geocoded")
        result['steps']['geocode'] = 'skipped'
    else:
        try:
            cmd = ["uv", "run", "holos", "pilot", "geocode-batch", "--csv-path", cleaned_path]
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            result['steps']['geocode'] = 'success'
            typer.echo(f"  ✓ Geocoded")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            result['steps']['geocode'] = f'failed: {str(e)}'
            typer.echo(f"  ✗ Failed: {e}")
            return result

    result['status'] = 'complete'
    return result


@app.command()
def expand_to_wards(
    start_ward: int = typer.Option(1, help="Starting ward number"),
    end_ward: int = typer.Option(1, help="Ending ward number"),
    year: int = typer.Option(2017, help="Year to process"),
    force: bool = typer.Option(False, help="Force reprocessing even if files exist"),
):
    """Expand the Ward 1 workflow to multiple wards.

    Runs the full pipeline for each ward and tracks success rates.

    Example:
      holos workflow expand-to-wards --start-ward 1 --end-ward 3 --year 2017
    """
    typer.echo(f"🔄 Expanding workflow to wards {start_ward}-{end_ward}, {year}...")
    typer.echo(f"  Force reprocessing: {force}\n")

    results = []
    successful_wards = 0
    failed_wards = 0

    for ward in range(start_ward, end_ward + 1):
        result = run_pipeline_for_ward(ward, year, force=force)
        results.append(result)

        if result.get('status') == 'complete':
            successful_wards += 1
        else:
            failed_wards += 1

    # Summary
    typer.echo(f"\n✓ Expansion complete")
    typer.echo(f"  Successful: {successful_wards}/{end_ward - start_ward + 1}")
    typer.echo(f"  Failed: {failed_wards}/{end_ward - start_ward + 1}")

    # Save results
    results_file = f"data/workflow_results_{year}_w{start_ward:02d}-w{end_ward:02d}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'metadata': {
                'start_ward': start_ward,
                'end_ward': end_ward,
                'year': year,
                'timestamp': datetime.now().isoformat(),
                'successful': successful_wards,
                'failed': failed_wards
            },
            'results': results
        }, f, indent=2)

    typer.echo(f"  Results: {results_file}")


@app.command()
def status(
    year: int = typer.Option(2017, help="Year to check status for"),
):
    """Show workflow status across all wards for a given year.

    Checks which wards have been processed and their status.

    Example:
      holos workflow status --year 2017
    """
    typer.echo(f"📊 Workflow status for {year}\n")

    wards_data = {}

    for ward in range(1, 51):
        csv_path = f"data/ward{ward:02d}_{year}_menu.csv"
        cleaned_path = f"data/ward{ward:02d}_{year}_menu_cleaned.csv"
        geocoded_path = f"data/ward{ward:02d}_{year}_menu_cleaned_geocoded.csv"

        status_str = "—"
        if Path(geocoded_path).exists():
            status_str = "✓ Complete"
        elif Path(cleaned_path).exists():
            status_str = "⊐ Validated"
        elif Path(csv_path).exists():
            status_str = "⊐ Extracted"

        if status_str != "—":
            wards_data[ward] = status_str

    # Print summary by status
    complete = sum(1 for s in wards_data.values() if 'Complete' in s)
    validated = sum(1 for s in wards_data.values() if 'Validated' in s)
    extracted = sum(1 for s in wards_data.values() if 'Extracted' in s)

    typer.echo(f"  Complete (geocoded): {complete}/50")
    typer.echo(f"  Validated: {validated}/50")
    typer.echo(f"  Extracted: {extracted}/50")
    typer.echo(f"  Not started: {50 - len(wards_data)}/50")
    typer.echo()

    # Show completed wards
    if complete > 0:
        complete_wards = [w for w, s in wards_data.items() if 'Complete' in s]
        typer.echo(f"✓ Completed: {', '.join(str(w) for w in sorted(complete_wards)[:10])}")
        if len(complete_wards) > 10:
            typer.echo(f"  ... and {len(complete_wards) - 10} more")


if __name__ == "__main__":
    app()
