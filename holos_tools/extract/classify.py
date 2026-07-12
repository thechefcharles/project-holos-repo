"""Step 2: Classify PDFs (text-native vs scanned) and route to extraction."""

import json
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict
import pdfplumber


@dataclass
class PDFClassification:
    """Classification result for a PDF."""
    doc_id: str
    source_path: str
    page_count: int
    total_chars: int
    avg_chars_per_page: float
    has_images: int
    classification: str  # "text-native" or "scanned"
    confidence: float  # 0.0–1.0
    extraction_method: str  # "pdfplumber" or "ocr"
    reasoning: str
    classified_at: str


def classify_pdf(pdf_path: Path, threshold_chars_per_page: int = 100) -> PDFClassification:
    """Classify a PDF as text-native or scanned.

    Uses heuristic: text-native PDFs have sufficient character content.
    Scanned PDFs are mostly images with little text.

    Args:
        pdf_path: Path to PDF file
        threshold_chars_per_page: Minimum avg chars/page for text-native classification

    Returns:
        PDFClassification dataclass with results and confidence score
    """
    from datetime import datetime

    doc_id = pdf_path.stem

    total_chars = 0
    total_images = 0
    page_count = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)

            for page in pdf.pages:
                # Count characters
                text = page.extract_text()
                if text:
                    total_chars += len(text)

                # Count images (heuristic for scanned)
                if hasattr(page, "images") and page.images:
                    total_images += len(page.images)

    except Exception as e:
        raise RuntimeError(f"Failed to classify {pdf_path}: {e}")

    # Calculate metrics
    avg_chars_per_page = total_chars / page_count if page_count > 0 else 0

    # Classification logic
    if avg_chars_per_page >= threshold_chars_per_page:
        classification = "text-native"
        extraction_method = "pdfplumber"
        # Confidence: higher if text is consistent, lower if few images
        confidence = min(0.99, 0.85 + (avg_chars_per_page / 1000) * 0.1)
        if total_images > 0:
            confidence -= (total_images / page_count) * 0.05
        confidence = max(0.7, confidence)
        reasoning = f"High text content ({avg_chars_per_page:.0f} chars/page, threshold {threshold_chars_per_page})"

    else:
        classification = "scanned"
        extraction_method = "ocr"
        # Confidence: higher if very few characters, lower if borderline
        if avg_chars_per_page < 10:
            confidence = 0.95
            reasoning = f"Very low text content ({avg_chars_per_page:.1f} chars/page)"
        else:
            confidence = 0.70 + (1 - avg_chars_per_page / threshold_chars_per_page) * 0.2
            reasoning = f"Low text content ({avg_chars_per_page:.0f} chars/page, below threshold {threshold_chars_per_page})"

    return PDFClassification(
        doc_id=doc_id,
        source_path=str(pdf_path),
        page_count=page_count,
        total_chars=int(total_chars),
        avg_chars_per_page=round(avg_chars_per_page, 1),
        has_images=total_images,
        classification=classification,
        confidence=round(confidence, 2),
        extraction_method=extraction_method,
        reasoning=reasoning,
        classified_at=datetime.utcnow().isoformat(),
    )


def classify_pdfs_in_directory(
    source_dir: Path,
    output_dir: Path,
    threshold_chars_per_page: int = 100,
) -> list:
    """Classify all PDFs in a directory and write classification JSONs.

    Args:
        source_dir: Directory containing PDFs
        output_dir: Directory to write classification JSONs
        threshold_chars_per_page: Classification threshold

    Returns:
        List of PDFClassification results
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(source_dir.glob("*.pdf"))
    results = []

    for pdf_path in pdfs:
        try:
            classification = classify_pdf(pdf_path, threshold_chars_per_page)
            results.append(classification)

            # Write classification JSON
            output_file = output_dir / f"{classification.doc_id}_classification.json"
            output_file.write_text(json.dumps(asdict(classification), indent=2))

        except Exception as e:
            print(f"  ✗ Error classifying {pdf_path.name}: {e}")

    return results
