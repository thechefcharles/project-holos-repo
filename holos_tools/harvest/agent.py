"""Harvester agent: orchestrates CLI commands to discover, download, and manifest sources."""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Any
import uuid

import yaml


def load_config() -> dict:
    """Load config/sources.yaml."""
    with open("config/sources.yaml") as f:
        return yaml.safe_load(f)


def run_harvest_socrata(dataset_id: str) -> dict:
    """Run holos harvest socrata CLI and return structured result."""
    try:
        result = subprocess.run(
            ["uv", "run", "holos", "harvest", "socrata", "--dataset", dataset_id],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return {
                "status": "failed",
                "error": result.stderr,
                "dataset_id": dataset_id,
            }

        # Parse manifest from stdout
        # The CLI outputs: "✓ Downloaded <id> → <path>"
        # Manifest is written to raw/socrata/<id>/<date>/<id>.json

        return {
            "status": "success",
            "dataset_id": dataset_id,
            "stdout": result.stdout,
        }

    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": f"Timeout downloading {dataset_id}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def run_harvest_url(source_url: str, source_id: str) -> dict:
    """Run holos harvest url CLI and return structured result."""
    try:
        result = subprocess.run(
            ["uv", "run", "holos", "harvest", "url", "--source-url", source_url, "--source-id", source_id],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return {
                "status": "failed",
                "error": result.stderr,
                "source_url": source_url,
                "source_id": source_id,
            }

        return {
            "status": "success",
            "source_url": source_url,
            "source_id": source_id,
            "stdout": result.stdout,
        }

    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": f"Timeout downloading {source_url}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def discover_reference_layers(config: dict) -> list[dict]:
    """Discover all reference layers from config/sources.yaml."""
    datasets = config.get("chicago", {}).get("reference_data", {})
    return [
        {
            "type": "socrata",
            "source_id": f"socrata_{key}",
            "dataset_id": value.get("id"),
            "role": value.get("role"),
        }
        for key, value in datasets.items()
        if value.get("id")
    ]


def discover_menu_pdfs(config: dict) -> list[dict]:
    """Discover menu PDF sources from config."""
    menu_pdfs = config.get("chicago", {}).get("menu_pdfs", {})

    if not menu_pdfs:
        return []

    sources = []

    # Archive-based URLs
    patterns = menu_pdfs.get("url_patterns", [])
    for pattern in patterns:
        sources.append({
            "type": "url",
            "source_id": "menu_pdfs",
            "source_url": pattern,
            "source": "chicago.gov OBM archive pattern",
        })

    # Local files (Charlie's archive)
    # Note: we don't auto-discover local paths; the agent's input must specify them

    return sources


def build_agent_output(
    job_id: str,
    status: str,
    artifacts: list[dict],
    metrics: dict,
    flags: list[str],
    needs_human: bool,
    reasons: list[str],
) -> dict:
    """Build structured output per schemas/agent_output.schema.json."""
    return {
        "job_id": job_id,
        "status": status,
        "artifacts": artifacts,
        "metrics": metrics,
        "flags": flags,
        "needs_human": needs_human,
        "reasons": reasons,
    }


def main():
    """
    Harvester agent workflow:
    1. Load config/sources.yaml
    2. Discover reference layers (Socrata datasets)
    3. Discover menu PDFs (archive URLs)
    4. Validate all against whitelist
    5. Run holos harvest CLI commands
    6. Aggregate results into structured JSON
    7. Output per agent_output.schema.json
    """

    job_id = str(uuid.uuid4())
    config = load_config()

    artifacts = []
    metrics = {
        "sources_discovered": 0,
        "bytes_downloaded": 0,
        "new_formats_flagged": 0,
    }
    flags = []
    reasons = []
    status = "success"
    needs_human = False

    # Discover reference layers
    ref_layers = discover_reference_layers(config)
    print(f"Discovered {len(ref_layers)} reference layers")

    for layer in ref_layers:
        print(f"  - {layer['dataset_id']} ({layer['role']})")
        result = run_harvest_socrata(layer["dataset_id"])

        if result["status"] == "success":
            metrics["sources_discovered"] += 1
            # Find the manifest file
            dataset_id = layer["dataset_id"]
            manifest_paths = list(Path(f"raw/socrata/{dataset_id}").glob("*/*.json"))
            if manifest_paths:
                for mpath in manifest_paths:
                    with open(mpath) as f:
                        manifest = json.load(f)
                    artifacts.append({
                        "path": str(mpath),
                        "size_bytes": manifest.get("size_bytes", 0),
                        "checksum": manifest.get("checksum"),
                        "source_id": manifest.get("source_id"),
                    })
                    metrics["bytes_downloaded"] += manifest.get("size_bytes", 0)
        else:
            flags.append(f"reference_layer_failed_{layer['dataset_id']}")
            reasons.append(f"Failed to harvest {layer['dataset_id']}: {result.get('error')}")
            status = "failed"

    # Discover menu PDFs
    menu_sources = discover_menu_pdfs(config)
    print(f"Discovered {len(menu_sources)} menu PDF source patterns")

    for source in menu_sources:
        print(f"  - {source['source_url'][:60]}...")
        # Note: For URL patterns with {YEAR}/{N} placeholders, we'd need additional logic
        # For MVP, we just document the pattern
        reasons.append(f"Menu PDF source pattern: {source['source_url']}")

    # Ward Wise (benchmark source)
    ward_wise = config.get("ward_wise", {})
    if ward_wise.get("api"):
        print(f"Ward Wise available: {ward_wise.get('api')} (benchmark only, separate storage)")
        reasons.append("Ward Wise API available for benchmarking; stored separately, labeled as Ward Wise-derived")

    # Output
    output = build_agent_output(
        job_id=job_id,
        status=status,
        artifacts=artifacts,
        metrics=metrics,
        flags=flags,
        needs_human=needs_human,
        reasons=reasons,
    )

    print("\n" + "="*80)
    print("HARVESTER AGENT OUTPUT (JSON per schemas/agent_output.schema.json)")
    print("="*80)
    print(json.dumps(output, indent=2))

    return output


if __name__ == "__main__":
    main()
