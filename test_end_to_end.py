#!/usr/bin/env python3
"""End-to-end test: 2012Menu.pdf through Normalize → Parse → Geocode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pdfplumber
from holos_tools.extract.normalize import extract_from_pdf_text

pdf_path = Path(__file__).parent / "raw/menu_pdfs/2026-07-12/2012Menu.pdf"

print("=" * 80)
print("VERTICAL SLICE TEST: 2012Menu.pdf through Normalize Pipeline")
print("=" * 80)

# STEP 1: NORMALIZE (Extract)
print("\nSTEP 1: NORMALIZE (Extract spending records from PDF)")
print("-" * 80)

with pdfplumber.open(pdf_path) as pdf:
    print(f"PDF has {len(pdf.pages)} pages")
    print(f"Extracting all text...")

    # Extract text from all pages
    full_text = "\n".join(pdf.pages[i].extract_text() or "" for i in range(len(pdf.pages)))
    print(f"Extracted {len(full_text):,} characters")

    # Normalize (extract records)
    print("Running normalization...")
    records = extract_from_pdf_text(full_text, 2012)

print(f"✓ Extracted {len(records):,} spending records\n")

# Summarize
by_category = {}
total_cost = 0
for r in records:
    by_category[r.category] = by_category.get(r.category, 0) + 1
    total_cost += r.cost

print(f"Summary by category:")
for cat in sorted(by_category.keys()):
    count = by_category[cat]
    print(f"  {cat:30s}: {count:4d} records")

print(f"\nTotal cost: ${total_cost:,.2f}")
print(f"Average per record: ${total_cost/len(records):,.2f}")

# Show sample records
print(f"\n\nSample records (first 30):")
for i, r in enumerate(records[:30], 1):
    print(f"{i:3d}. Ward {r.ward} | {r.category:25s} | ${r.cost:>12,.2f} | {r.location[:45]}")

print("\n" + "=" * 80)
print("✓ STEP 1 COMPLETE: Extraction successful")
print("=" * 80)
print("\nNEXT STEPS:")
print("  Step 2: Parse location strings into components (usaddress/libpostal)")
print("  Step 3: Geocode to coordinates using cascade")
print("  Step 4: Measure success rate (% records → coordinates)")
