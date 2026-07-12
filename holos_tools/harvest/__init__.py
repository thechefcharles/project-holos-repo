"""Harvest: discover, download, and manifest data sources (never parse)."""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
import typer
import yaml
from ..core import Config

app = typer.Typer(help="Harvest data sources (download + manifest only, never parse)")


def _load_sources_config() -> dict:
    """Load config/sources.yaml and return the config dict."""
    with open("config/sources.yaml") as f:
        return yaml.safe_load(f)


def _sha256_file(data: bytes) -> str:
    """Compute SHA256 checksum of bytes."""
    return hashlib.sha256(data).hexdigest()


def _compute_manifest(
    source_id: str, url: str, data: bytes, acquisition_method: str
) -> dict:
    """Build a manifest entry."""
    return {
        "source_id": source_id,
        "url": url,
        "checksum": f"sha256:{_sha256_file(data)}",
        "retrieved_at": datetime.utcnow().isoformat(),
        "size_bytes": len(data),
        "acquisition_method": acquisition_method,
    }


@app.command()
def socrata(
    dataset: str = typer.Option(..., help="Socrata dataset ID"),
):
    """Download a Socrata dataset reference layer and create a manifest.

    Whitelisted by config/sources.yaml. Idempotent: skips if checksum matches.
    """
    config = _load_sources_config()

    # Verify dataset is in config
    socrata_datasets = config.get("chicago", {}).get("datasets", {})
    if dataset not in socrata_datasets:
        typer.echo(f"✗ Dataset {dataset} not in config/sources.yaml", err=True)
        raise typer.Exit(1)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    source_dir = Path(f"raw/socrata/{dataset}/{timestamp}")
    source_dir.mkdir(parents=True, exist_ok=True)

    try:
        url = f"https://data.cityofchicago.org/api/views/{dataset}/rows.csv"
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        data = response.content

        filename = f"{dataset}.csv"
        filepath = source_dir / filename
        checksum = _sha256_file(data)

        # Idempotency: check if file exists with same checksum
        manifest_path = source_dir / f"{dataset}.json"
        if filepath.exists() and manifest_path.exists():
            existing_manifest = json.loads(manifest_path.read_text())
            if existing_manifest.get("checksum") == f"sha256:{checksum}":
                typer.echo(f"✓ Skipped {dataset} (already downloaded, checksum match)")
                return

        filepath.write_bytes(data)
        manifest = _compute_manifest(f"socrata_{dataset}", url, data, "socrata_api")
        manifest_path.write_text(json.dumps(manifest, indent=2))

        typer.echo(f"✓ Downloaded {dataset} → {filepath}")
        typer.echo(f"  Checksum: {checksum}")
        typer.echo(f"  Manifest: {manifest_path}")

    except httpx.HTTPError as e:
        typer.echo(f"✗ Download failed for {dataset}: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def url(
    source_url: str = typer.Option(..., help="URL or local file path to harvest"),
    source_id: str = typer.Option(..., help="Source registry ID"),
):
    """Download from URL or ingest local file; create manifest. Idempotent."""
    config = _load_sources_config()

    # Verify source is in config
    config_sources = config.get("chicago", {}).get("menu_pdfs", {})
    if source_id not in config_sources and source_id != "menu_pdfs":
        typer.echo(f"✗ Source {source_id} not in config/sources.yaml", err=True)
        raise typer.Exit(1)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    source_dir = Path(f"raw/{source_id}/{timestamp}")
    source_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Check if it's a local file
        local_path = Path(source_url)
        if local_path.exists() and local_path.is_file():
            data = local_path.read_bytes()
            filename = local_path.name
            acquisition = "local_file"
            url_for_manifest = f"file://{local_path.resolve()}"
        else:
            # Download from URL
            response = httpx.get(source_url, timeout=60.0)
            response.raise_for_status()
            data = response.content
            filename = source_url.split("/")[-1] or "download"
            acquisition = "http_download"
            url_for_manifest = source_url

        filepath = source_dir / filename
        checksum = _sha256_file(data)
        manifest_path = source_dir / f"{filename}.json"

        # Idempotency: skip if checksum matches
        if filepath.exists() and manifest_path.exists():
            existing_manifest = json.loads(manifest_path.read_text())
            if existing_manifest.get("checksum") == f"sha256:{checksum}":
                typer.echo(f"✓ Skipped {source_id}/{filename} (checksum match)")
                return

        filepath.write_bytes(data)
        manifest = _compute_manifest(source_id, url_for_manifest, data, acquisition)
        manifest_path.write_text(json.dumps(manifest, indent=2))

        typer.echo(f"✓ Harvested {source_id}/{filename} → {filepath}")
        typer.echo(f"  Checksum: {checksum}")
        typer.echo(f"  Manifest: {manifest_path}")

    except httpx.HTTPError as e:
        typer.echo(f"✗ Download failed for {source_url}: {e}", err=True)
        raise typer.Exit(1)
    except FileNotFoundError as e:
        typer.echo(f"✗ Local file not found: {source_url}", err=True)
        raise typer.Exit(1)


@app.command()
def discover(
    source_id: str = typer.Option("menu_pdfs", help="Source ID to discover (e.g., menu_pdfs)"),
    start_year: int = typer.Option(2012, help="Start year (inclusive)"),
    end_year: int = typer.Option(2026, help="End year (inclusive)"),
    dry_run: bool = typer.Option(False, help="List URLs without downloading"),
):
    """Discover and harvest PDFs from OBM/DBM archives by expanding URL patterns.

    Reads url_patterns from config/sources.yaml, expands with years/quarters,
    attempts to download each, and manifests successful downloads.
    """
    config = _load_sources_config()

    # Get source config
    source_config = config.get("chicago", {}).get(source_id)
    if not source_config:
        typer.echo(f"✗ Source {source_id} not in config/sources.yaml", err=True)
        raise typer.Exit(1)

    archive_base = source_config.get("archive_base")
    url_patterns = source_config.get("url_patterns", [])

    if not archive_base or not url_patterns:
        typer.echo(f"✗ Source {source_id} missing archive_base or url_patterns", err=True)
        raise typer.Exit(1)

    # Generate URLs by expanding patterns
    urls_to_try = []

    for pattern in url_patterns:
        if "{YEAR}" in pattern and "{N}" not in pattern:
            # Yearly pattern (old format)
            for year in range(start_year, end_year + 1):
                expanded = pattern.replace("{YEAR}", str(year))
                url = f"{archive_base}/{expanded}"
                urls_to_try.append(url)

        elif "{YEAR}" in pattern and "{N}" in pattern:
            # Quarterly pattern (new format)
            for year in range(start_year, end_year + 1):
                for quarter in range(1, 5):  # Q1–Q4
                    expanded = pattern.replace("{YEAR}", str(year)).replace("{N}", str(quarter))
                    url = f"{archive_base}/{expanded}"
                    urls_to_try.append(url)

        else:
            # No variables; use as-is
            url = f"{archive_base}/{pattern}"
            urls_to_try.append(url)

    typer.echo(f"📋 Generated {len(urls_to_try)} URLs to try from {len(url_patterns)} pattern(s)")

    if dry_run:
        typer.echo("\n🔍 DRY RUN: URLs to discover (not downloading):\n")
        for url in urls_to_try:
            typer.echo(f"  {url}")
        return

    # Download each URL
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    source_dir = Path(f"raw/{source_id}/{timestamp}")
    source_dir.mkdir(parents=True, exist_ok=True)

    results = {"success": 0, "skipped": 0, "not_found": 0, "error": 0}
    downloaded_files = []

    typer.echo(f"\n📥 Attempting to download from {len(urls_to_try)} URLs...\n")

    for i, url in enumerate(urls_to_try, 1):
        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)

            if response.status_code == 404:
                typer.echo(f"  [{i:3d}] ✗ 404 Not Found: {url}")
                results["not_found"] += 1
                continue

            response.raise_for_status()
            data = response.content

            # Extract filename from URL
            filename = url.split("/")[-1]
            if not filename or "?" in filename:
                filename = f"page_{i}.pdf"

            filepath = source_dir / filename
            checksum = _sha256_file(data)
            manifest_path = source_dir / f"{filename}.json"

            # Idempotency: skip if checksum matches
            if filepath.exists() and manifest_path.exists():
                existing_manifest = json.loads(manifest_path.read_text())
                if existing_manifest.get("checksum") == f"sha256:{checksum}":
                    typer.echo(f"  [{i:3d}] ⊘ Already have: {filename}")
                    results["skipped"] += 1
                    continue

            # Write file and manifest
            filepath.write_bytes(data)
            manifest = _compute_manifest(source_id, url, data, "http_discovery")
            manifest_path.write_text(json.dumps(manifest, indent=2))

            typer.echo(f"  [{i:3d}] ✓ Downloaded: {filename} ({len(data):,} bytes)")
            results["success"] += 1
            downloaded_files.append(filename)

        except httpx.TimeoutException:
            typer.echo(f"  [{i:3d}] ✗ Timeout: {url}")
            results["error"] += 1
        except httpx.HTTPError as e:
            typer.echo(f"  [{i:3d}] ✗ HTTP Error: {url} ({e})")
            results["error"] += 1
        except Exception as e:
            typer.echo(f"  [{i:3d}] ✗ Error: {url} ({str(e)[:60]})")
            results["error"] += 1

    # Summary
    typer.echo(f"\n{'─'*70}")
    typer.echo(f"📊 Discovery Summary:")
    typer.echo(f"  ✓ Downloaded: {results['success']} PDFs")
    typer.echo(f"  ⊘ Already have: {results['skipped']} PDFs (checksum match)")
    typer.echo(f"  ✗ Not found (404): {results['not_found']} URLs")
    typer.echo(f"  ✗ Errors: {results['error']} URLs")
    typer.echo(f"  📁 Stored in: {source_dir.resolve()}")
    typer.echo(f"{'─'*70}")

    if results["success"] == 0 and results["skipped"] == 0:
        typer.echo(f"\n⚠️  No PDFs downloaded or found. Check archive_base and patterns in config/sources.yaml")
        raise typer.Exit(1)
