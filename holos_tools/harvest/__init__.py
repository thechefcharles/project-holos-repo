"""Harvest: discover, download, and manifest data sources."""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
import typer
from ..core import Config, insert_source_record

app = typer.Typer(help="Harvest data sources (download, manifest, validate)")


@app.command()
def socrata(
    dataset_id: str = typer.Option(..., help="Socrata dataset ID"),
    output_dir: str = typer.Option("raw/sources", help="Output directory"),
    source_id: str = typer.Option(None, help="Source registry ID (auto-detect if not provided)"),
):
    """Download a Socrata dataset and create a manifest."""
    config = Config()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        url = f"https://data.cityofchicago.org/api/views/{dataset_id}/rows.csv"
        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()

        timestamp = datetime.utcnow().isoformat()
        filename = f"{dataset_id}-{timestamp.split('T')[0]}.csv"
        filepath = output_path / filename

        filepath.write_bytes(response.content)
        checksum = hashlib.sha256(response.content).hexdigest()

        manifest = {
            "source_id": source_id or f"socrata_{dataset_id}",
            "url": url,
            "checksum": f"sha256:{checksum}",
            "retrieved_at": timestamp,
            "dataset_id": dataset_id,
            "size_bytes": len(response.content),
        }

        manifest_path = filepath.with_suffix(".json")
        manifest_path.write_text(json.dumps(manifest, indent=2))

        typer.echo(f"✓ Downloaded {dataset_id} → {filepath}")
        typer.echo(f"  Checksum: {checksum}")
        typer.echo(f"  Manifest: {manifest_path}")

    except Exception as e:
        typer.echo(f"✗ Failed to harvest {dataset_id}: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def url(
    source_url: str = typer.Option(..., help="URL to download"),
    output_dir: str = typer.Option("raw/sources", help="Output directory"),
    source_id: str = typer.Option(..., help="Source registry ID"),
):
    """Download from a URL and create a manifest."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        response = httpx.get(source_url, timeout=60.0)
        response.raise_for_status()

        timestamp = datetime.utcnow().isoformat()
        filename = f"{source_id}-{timestamp.split('T')[0]}"
        if "." not in source_url.split("/")[-1]:
            filename += ".bin"
        else:
            filename = source_url.split("/")[-1]

        filepath = output_path / filename
        filepath.write_bytes(response.content)
        checksum = hashlib.sha256(response.content).hexdigest()

        manifest = {
            "source_id": source_id,
            "url": source_url,
            "checksum": f"sha256:{checksum}",
            "retrieved_at": timestamp,
            "size_bytes": len(response.content),
        }

        manifest_path = filepath.with_suffix(".json")
        manifest_path.write_text(json.dumps(manifest, indent=2))

        typer.echo(f"✓ Downloaded {source_id} → {filepath}")
        typer.echo(f"  Checksum: {checksum}")

    except Exception as e:
        typer.echo(f"✗ Failed to download {source_url}: {e}", err=True)
        raise typer.Exit(1)
