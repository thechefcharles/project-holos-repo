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
