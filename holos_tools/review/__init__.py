"""Review: human-in-the-loop validation and promotion workflows."""

import json
from pathlib import Path
import typer
from holos_tools.core import Config, HolosDB

app = typer.Typer(help="Review extracted features and promote to core schema")


@app.command()
def list_staging(
    limit: int = typer.Option(50, help="Max features to show"),
    offset: int = typer.Option(0, help="Pagination offset"),
):
    """List staging features awaiting review."""
    from .subsurface import SubsurfaceReviewer

    config = Config()
    db = HolosDB(config.db_url)
    reviewer = SubsurfaceReviewer(db)

    features = reviewer.get_staging_features(limit=limit, offset=offset)

    if not features:
        typer.echo("✓ No features in staging (all reviewed or no extraction yet)")
        return

    typer.echo(f"\n=== Subsurface Features Awaiting Review ({len(features)} shown) ===\n")
    for i, feat in enumerate(features, start=1):
        typer.echo(f"{i}. {feat['name_raw']}")
        typer.echo(f"   Type: {feat['feature_type_raw']} → {feat['feature_type']}")
        typer.echo(f"   Depth: {feat['depth_raw']} → {feat['depth_normalized']}m")
        typer.echo(f"   QL: {feat['ql_level']} | Conf: {feat['extraction_conf']:.2f}")
        if feat.get("needs_review"):
            typer.echo(f"   ⚠ Needs review: {feat['review_reason']}")
        typer.echo(f"   ID: {feat['extracted_id']}")
        typer.echo()


@app.command()
def approve(
    extracted_id: str = typer.Option(..., help="Staging feature ID to approve"),
    reviewed_by: str = typer.Option("holos_cli", help="Reviewer name/ID"),
    depth_override: float = typer.Option(None, help="Override normalized depth (meters)"),
    ql_override: str = typer.Option(None, help="Override QL level (QL-A, QL-B, QL-C, QL-D)"),
    notes: str = typer.Option(None, help="Review notes"),
):
    """Approve a staging feature and promote to core.subsurface_features."""
    from .subsurface import SubsurfaceReviewer

    config = Config()
    db = HolosDB(config.db_url)
    reviewer = SubsurfaceReviewer(db)

    result = reviewer.approve_feature(
        extracted_id, reviewed_by, notes, depth_override, ql_override
    )

    if result["status"] == "approved":
        typer.echo(
            f"✓ Feature approved and promoted to core"
        )
        typer.echo(f"  Feature ID: {result['feature_id']}")
        typer.echo(f"  QL level: {result['ql_level']}")
        typer.echo(f"  Depth: {result['depth_normalized']}m")
    else:
        typer.echo(f"✗ Approval failed: {result['reason']}", err=True)
        raise typer.Exit(1)


@app.command()
def reject(
    extracted_id: str = typer.Option(..., help="Staging feature ID to reject"),
    reviewed_by: str = typer.Option("holos_cli", help="Reviewer name/ID"),
    reason: str = typer.Option(..., help="Reason for rejection"),
):
    """Reject a staging feature (mark as reviewed, not promoted)."""
    from .subsurface import SubsurfaceReviewer

    config = Config()
    db = HolosDB(config.db_url)
    reviewer = SubsurfaceReviewer(db)

    result = reviewer.reject_feature(extracted_id, reviewed_by, reason)

    if result["status"] == "rejected":
        typer.echo(f"✓ Feature rejected")
        typer.echo(f"  Reason: {result['reason']}")
    else:
        typer.echo(f"✗ Rejection failed: {result['reason']}", err=True)
        raise typer.Exit(1)


@app.command()
def escalate(
    extracted_id: str = typer.Option(..., help="Staging feature ID to escalate"),
    reviewed_by: str = typer.Option("holos_cli", help="Reviewer name/ID"),
    reason: str = typer.Option(..., help="Reason for escalation"),
):
    """Escalate a feature for expert review (QL-A evidence, legal review, etc.)."""
    from .subsurface import SubsurfaceReviewer

    config = Config()
    db = HolosDB(config.db_url)
    reviewer = SubsurfaceReviewer(db)

    result = reviewer.escalate_feature(extracted_id, reviewed_by, reason)

    if result["status"] == "escalated":
        typer.echo(f"✓ Feature escalated for expert review")
        typer.echo(f"  Review item ID: {result['review_item_id']}")
        typer.echo(f"  Reason: {result['reason']}")
    else:
        typer.echo(f"✗ Escalation failed: {result['reason']}", err=True)
        raise typer.Exit(1)


@app.command()
def stats():
    """Show review queue statistics."""
    from .subsurface import SubsurfaceReviewer

    config = Config()
    db = HolosDB(config.db_url)
    reviewer = SubsurfaceReviewer(db)

    stats = reviewer.get_review_stats()

    typer.echo("\n=== Subsurface Review Queue Statistics ===\n")
    typer.echo(f"Total features in staging: {stats.get('total_features', 0)}")
    typer.echo(f"Needing review: {stats.get('needs_review_count', 0)}")
    typer.echo(f"QL-D (low confidence): {stats.get('ql_d_count', 0)}")
    typer.echo(f"QL-C (reference data): {stats.get('ql_c_count', 0)}")
    typer.echo(f"Avg extraction confidence: {stats.get('avg_extraction_conf', 0):.2f}")
    typer.echo()
