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


# NOTE: B1 (pdf_vector), B2 (raster_plate), B3 (native_cad) extraction chains
# are Phase 3 work — frozen in phase3/ folder until Phase 1 complete.
# They will be re-integrated after Phase 1 (civic spending map) ships.
