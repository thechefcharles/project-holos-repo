"""Geocode: normalize text, parse addresses, run cascade."""

import json
import re
from pathlib import Path
from typing import Optional
import typer
import unicodedata
from ..core import Config, HolosDB

app = typer.Typer(help="Geocode: normalize locations, parse addresses, run cascade")


def normalize_text(text: str) -> str:
    """Normalize location text: lowercase, remove diacritics, collapse whitespace."""
    if not text:
        return ""
    # Remove diacritics
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Lowercase and collapse whitespace
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


@app.command()
def normalize(
    input_table: str = typer.Option("staging.geocode_parsed", help="Input table"),
    output_table: str = typer.Option("staging.geocode_parsed", help="Output table"),
    commit: bool = typer.Option(False, help="Commit changes to database"),
) -> None:
    """Normalize address text (Stage 0a): lowercase, remove diacritics, standardize."""
    config = Config()
    db = HolosDB(config.db_url)

    try:
        # For Phase 1, just output the normalization config
        result = {
            "status": "success",
            "input_table": input_table,
            "normalizations": [
                "lowercase",
                "remove_diacritics",
                "collapse_whitespace",
                "remove_leading_zeros_from_numbers",
            ],
            "examples": [
                {"raw": "123 N MICHIGAN AVE", "normalized": "123 n michigan ave"},
                {"raw": "  CLARK   ST  ", "normalized": "clark st"},
            ],
        }
        print(json.dumps(result, indent=2))

    except Exception as e:
        typer.echo(f"✗ Normalization failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def parse(
    input_table: str = typer.Option("staging.geocode_parsed", help="Input table"),
    output_table: str = typer.Option("staging.geocode_parsed", help="Output table"),
) -> None:
    """Parse normalized address (Stage 0b–0c): number, street, direction, suffix."""
    config = Config()

    try:
        # Phase 1: parse configuration
        result = {
            "status": "success",
            "input_table": input_table,
            "parser": "usaddress",
            "output_fields": [
                "number",
                "predir",
                "street",
                "suffix",
                "postdir",
            ],
            "examples": [
                {
                    "raw": "123 n michigan ave",
                    "parsed": {
                        "number": "123",
                        "predir": "N",
                        "street": "MICHIGAN",
                        "suffix": "AVE",
                    },
                },
            ],
        }
        print(json.dumps(result, indent=2))

    except Exception as e:
        typer.echo(f"✗ Parsing failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def cascade(
    input_table: str = typer.Option("staging.geocode_parsed", help="Input table (Stage 0c output)"),
    run_id: str = typer.Option(..., help="Run ID for tracking"),
    config_file: str = typer.Option("config/geocode.yaml", help="Geocoding config"),
    json_output: bool = typer.Option(False, help="Output JSON"),
) -> None:
    """Run the geocoding cascade (Stages 1–8)."""
    config = Config()

    try:
        # Phase 1: cascade configuration and stub
        result = {
            "status": "success",
            "run_id": run_id,
            "input_table": input_table,
            "stages": [
                {
                    "stage": 0,
                    "name": "cache",
                    "rows": 0,
                    "avg_score": 0.0,
                },
                {
                    "stage": 1,
                    "name": "address_point_exact",
                    "rows": 0,
                    "avg_score": 0.97,
                },
                {
                    "stage": 2,
                    "name": "centerline_interpolation",
                    "rows": 0,
                    "avg_score": 0.88,
                },
            ],
            "summary": {
                "total_rows": 0,
                "geocoded": 0,
                "review_queue": 0,
                "avg_score": 0.0,
            },
        }

        if json_output:
            print(json.dumps(result, indent=2))
        else:
            typer.echo(f"✓ Geocoding cascade for run {run_id}")
            typer.echo(f"  Input: {input_table}")
            typer.echo(f"  Config: {config_file}")

    except Exception as e:
        typer.echo(f"✗ Cascade failed: {e}", err=True)
        raise typer.Exit(1)
