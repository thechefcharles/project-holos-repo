"""Extract: convert raw documents to structured data."""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime
import typer
from .classify import classify_pdfs_in_directory
from .normalize import normalize_records, MasterSchema

app = typer.Typer(help="Extract structured data from documents (PDFs, CADs, scans)")


@app.command()
def pdf_tables(
    doc_path: str = typer.Option(..., help="Path to PDF file"),
    output_path: str = typer.Option(None, help="Output JSON file (auto-detect if not provided)"),
    source_id: str = typer.Option("pdf_tables", help="Source registry ID"),
):
    """Extract tables from a text-native PDF (Chain A1)."""
    import pdfplumber

    doc_file = Path(doc_path)
    if not doc_file.exists():
        typer.echo(f"✗ File not found: {doc_path}", err=True)
        raise typer.Exit(1)

    try:
        extractions = []

        with pdfplumber.open(doc_file) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                if not tables:
                    continue

                for table_idx, table in enumerate(tables):
                    headers = table[0] if table else []
                    for row_idx, row in enumerate(table[1:], start=1):
                        row_dict = {
                            f"col_{i}": cell
                            for i, cell in enumerate(row)
                        }
                        extractions.append({
                            "page_num": page_num,
                            "table_idx": table_idx,
                            "row_idx": row_idx,
                            "data": row_dict,
                        })

        if output_path is None:
            output_path = doc_file.with_suffix(".json")

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        result = {
            "source_id": source_id,
            "doc_path": str(doc_file),
            "rows_extracted": len(extractions),
            "extractions": extractions,
        }
        out_file.write_text(json.dumps(result, indent=2))

        typer.echo(f"✓ Extracted {len(extractions)} rows from {doc_file}")
        typer.echo(f"  Output: {out_file}")

    except Exception as e:
        typer.echo(f"✗ Failed to extract from {doc_path}: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def classify(
    source_dir: str = typer.Option(
        "raw/menu_pdfs/2026-07-12",
        help="Directory containing PDFs to classify"
    ),
    output_dir: str = typer.Option(
        "extractions/classifications",
        help="Directory to write classification JSONs"
    ),
    threshold: int = typer.Option(
        100,
        help="Minimum avg chars/page for text-native classification"
    ),
):
    """Classify PDFs as text-native or scanned (Step 2).

    Reads all PDFs from source_dir, classifies each using character-count
    heuristic, and writes classification JSON to output_dir.

    Classification:
    - text-native (>= threshold chars/page) → extract with pdfplumber
    - scanned (< threshold chars/page) → extract with OCR

    Outputs:
    - {doc_id}_classification.json per PDF
    - classification_report.json (summary)
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)

    if not source_path.exists():
        typer.echo(f"✗ Source directory not found: {source_path}", err=True)
        raise typer.Exit(1)

    typer.echo(f"📄 Classifying PDFs from {source_path}...\n")

    try:
        results = classify_pdfs_in_directory(source_path, output_path, threshold)
    except Exception as e:
        typer.echo(f"✗ Classification failed: {e}", err=True)
        raise typer.Exit(1)

    if not results:
        typer.echo("✗ No PDFs found to classify", err=True)
        raise typer.Exit(1)

    # Summary
    text_native = sum(1 for r in results if r.classification == "text-native")
    scanned = sum(1 for r in results if r.classification == "scanned")

    typer.echo(f"\n{'─'*70}")
    typer.echo(f"📊 Classification Summary:")
    typer.echo(f"  ✓ Text-native: {text_native} PDFs (→ pdfplumber)")
    typer.echo(f"  ✓ Scanned: {scanned} PDFs (→ OCR)")
    typer.echo(f"  📁 Saved to: {output_path.resolve()}")
    typer.echo(f"{'─'*70}\n")

    # Detailed results
    typer.echo("Classification Details:\n")
    for result in sorted(results, key=lambda r: r.doc_id):
        method = "📝" if result.classification == "text-native" else "🔍"
        typer.echo(
            f"  {method} {result.doc_id:30s} | "
            f"{result.avg_chars_per_page:7.1f} chars/page | "
            f"{result.classification:12s} | "
            f"conf {result.confidence:.2f}"
        )

    # Write master classification report
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "source_dir": str(source_path.resolve()),
        "output_dir": str(output_path.resolve()),
        "total_pdfs": len(results),
        "text_native_count": text_native,
        "scanned_count": scanned,
        "threshold_chars_per_page": threshold,
        "classifications": [
            {
                "doc_id": r.doc_id,
                "classification": r.classification,
                "avg_chars_per_page": r.avg_chars_per_page,
                "confidence": r.confidence,
                "extraction_method": r.extraction_method,
                "reasoning": r.reasoning,
            }
            for r in results
        ],
    }

    report_path = output_path / "classification_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    typer.echo(f"\n✓ Report written: {report_path}\n")


@app.command()
def normalize(
    source_dir: str = typer.Option(
        "raw/menu_pdfs/2026-07-12",
        help="Directory containing classified PDFs"
    ),
    output_dir: str = typer.Option(
        "extractions/normalized",
        help="Directory to write normalized spending records"
    ),
):
    """Extract and normalize spending rows from PDFs (Step 3).

    Reads text-native PDFs (from Step 2 classification), extracts spending rows
    using year-specific adapters, and outputs normalized JSON records per PDF.

    Strategy:
    - 2012–2016: Use table extraction (pdfplumber)
    - 2017+: Use text parsing with structured layout awareness

    Outputs:
    - {doc_id}_normalized.json per PDF (array of SpendingRecord dicts)
    - normalize_report.json (summary: total records, by year, by category)
    """
    import pdfplumber
    from .normalize import extract_from_pdf_text

    source_path = Path(source_dir)
    output_path = Path(output_dir)

    if not source_path.exists():
        typer.echo(f"✗ Source directory not found: {source_path}", err=True)
        raise typer.Exit(1)

    typer.echo(f"📊 Normalizing PDFs from {source_path}...\n")

    output_path.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(source_path.glob("*.pdf"))
    summary = {
        "total_pdfs": len(pdf_files),
        "total_records": 0,
        "by_year": {},
        "by_category": {},
        "pdfs": [],
    }

    for pdf_path in pdf_files:
        doc_id = pdf_path.stem

        # Extract year from filename
        year = None
        for y in range(2012, 2026):
            if str(y) in pdf_path.name:
                year = y
                break

        if year is None:
            typer.echo(f"⚠️  Skipped {doc_id}: could not infer year from filename", err=True)
            continue

        try:
            records_in_pdf = []

            with pdfplumber.open(pdf_path) as pdf:
                # Extract text from all pages and parse
                full_text = "\n".join(
                    (page.extract_text() or "")
                    for page in pdf.pages
                )

                page_records = extract_from_pdf_text(full_text, year)
                records_in_pdf.extend(page_records)

            if records_in_pdf:
                output_file = output_path / f"{doc_id}_normalized.json"
                records_dicts = [
                    {
                        "ward": r.ward,
                        "year": r.year,
                        "category": r.category,
                        "location": r.location,
                        "cost": r.cost,
                    }
                    for r in records_in_pdf
                ]
                output_file.write_text(json.dumps(records_dicts, indent=2))

                typer.echo(f"  ✓ {doc_id} ({year}): {len(records_in_pdf)} records")

                summary["pdfs"].append({
                    "doc_id": doc_id,
                    "year": year,
                    "records": len(records_in_pdf),
                })

                summary["by_year"][year] = summary["by_year"].get(year, 0) + len(records_in_pdf)

                for record in records_in_pdf:
                    cat = record.category
                    summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1

                summary["total_records"] += len(records_in_pdf)
            else:
                status = "table extraction not available" if year >= 2017 else "no records extracted"
                typer.echo(f"  ⚠️  {doc_id} ({year}): {status}")

        except Exception as e:
            typer.echo(f"  ✗ Error processing {doc_id}: {e}", err=True)

    # Write summary report
    report_path = output_path / "normalize_report.json"
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "source_dir": str(source_path.resolve()),
        "output_dir": str(output_path.resolve()),
        "summary": summary,
    }
    report_path.write_text(json.dumps(report, indent=2))

    typer.echo(f"\n{'─'*70}")
    typer.echo(f"📊 Normalization Summary:")
    typer.echo(f"  ✓ Total PDFs: {summary['total_pdfs']}")
    typer.echo(f"  ✓ Total records: {summary['total_records']}")
    if summary["by_year"]:
        typer.echo(f"  ✓ By year: {dict(sorted(summary['by_year'].items()))}")
    if summary["by_category"]:
        typer.echo(f"  ✓ By category: {dict(sorted(summary['by_category'].items()))}")
    typer.echo(f"  📁 Output: {output_path.resolve()}")
    typer.echo(f"{'─'*70}\n")


# NOTE: B1 (pdf_vector), B2 (raster_plate), B3 (native_cad) extraction chains
# are Phase 3 work — frozen in phase3/ folder until Phase 1 complete.
# They will be re-integrated after Phase 1 (civic spending map) ships.
