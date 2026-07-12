"""Extract: convert raw documents to structured data."""

import json
from pathlib import Path
from typing import Optional
import typer

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
def pdf_vector(
    doc_path: str = typer.Option(..., help="Path to CAD-exported PDF"),
    output_path: str = typer.Option(None, help="Output JSON file"),
    source_id: str = typer.Option("pdf_vector", help="Source registry ID"),
):
    """Extract vector linework from a CAD-exported PDF (Chain B1)."""
    from .b1_vector import B1VectorExtractor

    doc_file = Path(doc_path)
    if not doc_file.exists():
        typer.echo(f"✗ File not found: {doc_path}", err=True)
        raise typer.Exit(1)

    try:
        extractor = B1VectorExtractor()
        result = extractor.extract(str(doc_file))
        result["source_id"] = source_id

        if output_path is None:
            output_path = doc_file.with_stem(doc_file.stem + "_features").with_suffix(".json")

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(result, indent=2))

        typer.echo(f"✓ Extracted {result['features_extracted']} features from {doc_file}")
        typer.echo(f"  Confidence: {result['extraction_conf']:.2f}")
        typer.echo(f"  Output: {out_file}")

        if result["needs_review"]:
            typer.echo(f"  ⚠ Needs review: {result['reasons']}")

    except Exception as e:
        typer.echo(f"✗ Failed to extract from {doc_path}: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def plate(
    doc_path: str = typer.Option(..., help="Path to scanned plate/map image"),
    output_path: str = typer.Option(None, help="Output JSON file"),
    source_id: str = typer.Option("plate", help="Source registry ID"),
):
    """Extract features from a scanned map or utility plate (Chain B2/B3)."""
    doc_file = Path(doc_path)
    if not doc_file.exists():
        typer.echo(f"✗ File not found: {doc_path}", err=True)
        raise typer.Exit(1)

    try:
        result = {
            "source_id": source_id,
            "doc_path": str(doc_file),
            "extraction_method": "plate_ocr_stub",
            "features": [],
            "notes": "Plate OCR/line extraction requires tesseract or paddleocr integration",
        }

        if output_path is None:
            output_path = doc_file.with_stem(doc_file.stem + "_features").with_suffix(".json")

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(result, indent=2))

        typer.echo(f"✓ Plate extraction stub for {doc_file}")
        typer.echo(f"  Output: {out_file}")

    except Exception as e:
        typer.echo(f"✗ Failed to extract from plate {doc_path}: {e}", err=True)
        raise typer.Exit(1)
