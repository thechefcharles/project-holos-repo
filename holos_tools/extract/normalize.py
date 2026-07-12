"""Step 3: Normalize aldermanic menu spending to master schema.

Master schema (canonical):
  - ward: integer (1-50)
  - year: integer (2012-2025)
  - category: string (program/project type, normalized)
  - location: string (address or intersection)
  - cost: float (estimated cost in dollars)

Year-variant adapters handle layout differences across decades.
Uses table extraction when available, text parsing as fallback.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SpendingRecord:
    """Canonical spending record (master schema)."""
    ward: int
    year: int
    category: str
    location: str
    cost: float
    source_text: str = ""


class MasterSchema:
    """Master schema definition for aldermanic menu spending."""

    # Canonical category mappings (normalize variant names)
    CATEGORY_REMAP = {
        "alley resurfacing menu": "Alley Resurfacing",
        "alley speed hump menu": "Alley Speed Hump",
        "arterial street bump outs menu": "Arterial Street Bump Outs",
        "concrete alley menu": "Concrete Alley",
        "sidewalk repair menu": "Sidewalk Repair",
        "tree trimming menu": "Tree Trimming",
        # Add more mappings as needed
    }

    @classmethod
    def normalize_category(cls, raw_category: str) -> str:
        """Normalize category string to canonical form."""
        key = raw_category.lower().strip()
        return cls.CATEGORY_REMAP.get(key, raw_category)

    @classmethod
    def parse_cost(cls, cost_str: str) -> float:
        """Parse cost string (e.g., '$6,354.00') to float."""
        if not cost_str:
            return 0.0
        # Remove currency symbols, commas, and whitespace
        cleaned = re.sub(r'[$,\s]', '', cost_str.strip())
        try:
            return float(cleaned)
        except ValueError:
            return 0.0


class MenuAdapter2012:
    """Adapter for 2012 menu format."""

    @staticmethod
    def parse_row(text: str, ward: int, year: int, category: str = "Unknown") -> Optional[SpendingRecord]:
        """Parse a 2012 format row.

        Actual format (from PDF): Full Address ... Blocks Cost
        Example: "ON N MAPLEWOOD AVE FROM W BELDEN AV (2300 N) TO W 0.00 $19,882.00"

        Note: 'Desc Of Work' is NOT in data rows, only in headers.
        """
        text = text.strip()
        if not text or "$" not in text:
            return None

        # Extract cost from the end (rightmost $ amount)
        cost_match = re.search(r'\$[\d,\.]+', text)
        if not cost_match:
            return None

        cost_str = cost_match.group(0)
        cost = MasterSchema.parse_cost(cost_str)
        if cost == 0.0:
            return None

        # Extract location (everything before the cost, stripped of trailing numbers)
        cost_start = text.rfind('$')
        pre_cost = text[:cost_start].strip()

        # The last numeric value before the cost is typically blocks/unit count
        # Remove trailing numeric values (0.00, 1.00, etc.)
        location = re.sub(r'\s+[\d.]+\s*$', '', pre_cost).strip()

        if not location:
            return None

        return SpendingRecord(
            ward=ward,
            year=year,
            category=MasterSchema.normalize_category(category),
            location=location,
            cost=cost,
            source_text=text,
        )


class MenuAdapter2017Plus:
    """Adapter for 2017+ menu format (simplified).

    Format: MenuPackage | Locations | Estimated Cost
    """

    @staticmethod
    def parse_row(text: str, ward: int, year: int) -> Optional[SpendingRecord]:
        """Parse a 2017+ format row."""
        # Pattern: "Category (code) (year) Locations $Cost"
        # Example: "Alley Resurfacing Menu (1-1) (2017) W CHICAGO AVE & N BISHOP ST&W FRY ST & N GREENVIEW AVE $12,838.1"

        # Extract cost (rightmost $ amount)
        cost_match = re.search(r'\$[\d,\.]+', text)
        if not cost_match:
            return None

        cost_str = cost_match.group(0)
        cost = MasterSchema.parse_cost(cost_str)
        if cost == 0.0:
            return None

        # Extract category (text before first parenthesis)
        category_match = re.match(r'^([^(]+)', text)
        category = category_match.group(1).strip() if category_match else "Unknown"

        # Extract location (text between cost and end, or between category and cost)
        # This is tricky; for now, extract everything between category and cost
        category_end = text.find('(') if '(' in text else len(category)
        cost_start = text.rfind('$')
        location_text = text[category_end:cost_start].strip()

        # Clean up location (remove parenthetical year codes)
        location = re.sub(r'\([^)]+\)', '', location_text).strip()

        if not location:
            return None

        return SpendingRecord(
            ward=ward,
            year=year,
            category=MasterSchema.normalize_category(category),
            location=location,
            cost=cost,
            source_text=text,
        )


def get_adapter_for_year(year: int) -> type:
    """Select adapter based on year."""
    if 2012 <= year <= 2016:
        return MenuAdapter2012
    else:  # 2017+
        return MenuAdapter2017Plus


def extract_ward_from_table_row(row: List) -> Optional[int]:
    """Extract ward number from table header row.

    Header format: "2012 Ward : 1" or "Ward: 1"
    """
    if not row or not row[0]:
        return None

    text = str(row[0]).strip()

    # Try patterns like "2012 Ward : 1" or "Ward: 1"
    match = re.search(r'Ward\s*:\s*(\d+)', text)
    if match:
        return int(match.group(1))

    return None


def extract_category_from_table_row(row: List) -> Optional[str]:
    """Extract program/category from table header row.

    Header format: "Program : Curb & Gutter Menu"
    """
    if not row or not row[0]:
        return None

    text = str(row[0]).strip()

    # Try pattern like "Program : Curb & Gutter Menu"
    match = re.search(r'Program\s*:\s*(.+?)(?:\n|$)', text)
    if match:
        return match.group(1).strip()

    # Also try just extracting after colon (2017+ format)
    if ":" in text:
        parts = text.split(":", 1)
        if len(parts) > 1:
            return parts[1].strip()

    return text


def normalize_records(raw_records: List[Dict], year: int) -> List[SpendingRecord]:
    """Normalize a list of raw spending records to master schema.

    Args:
        raw_records: List of dicts with keys: ward, text, etc.
        year: Year for these records

    Returns:
        List of normalized SpendingRecord objects
    """
    adapter = get_adapter_for_year(year)
    normalized = []

    for record in raw_records:
        ward = record.get("ward")
        text = record.get("text", "")

        if not ward or not text:
            continue

        try:
            parsed = adapter.parse_row(text, ward, year)
            if parsed:
                normalized.append(parsed)
        except Exception:
            pass

    return normalized


def extract_from_pdf_text(text: str, year: int) -> List[SpendingRecord]:
    """Extract spending records from PDF text.

    Handles wrapped addresses by looking ahead for cost markers.
    """
    records = []
    lines = [line.strip() for line in text.split("\n")]
    lines = [l for l in lines if l]  # Remove empty lines

    current_ward = None
    current_category = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip page footers/headers
        if re.match(r'^[\d/]+\s+[\d:]+\s+(AM|PM)', line) or ("Page" in line and "of" in line):
            i += 1
            continue

        # Skip document headers
        if any(x in line for x in ["CONSTRUCTION MANAGEMENT", "Menu Detail by Ward", "MENU WARD DETAIL REPORT"]):
            i += 1
            continue

        # Detect ward header
        if "Ward" in line and ":" in line and "Full Address" not in line:
            ward_match = re.search(r'Ward\s*:\s*(\d+)', line)
            if ward_match:
                current_ward = int(ward_match.group(1))
            i += 1
            continue

        # Detect program/category header
        if "Program" in line and ":" in line:
            prog_match = re.search(r'Program\s*:\s*(.+?)(?:\s*\n|$)', line)
            if prog_match:
                current_category = prog_match.group(1).strip()
                current_category = current_category.replace("\nMenu", "").replace(" Menu", "")
            i += 1
            continue

        # Skip column headers and summaries
        if any(x in line for x in ["Full Address", "Desc Of Work", "CDOT :", "OBM :"]):
            i += 1
            continue

        # Check if this line contains a cost marker
        if "$" in line:
            # This is a complete record (possibly with wrapped lines before it)
            # Look back to see if there's an accumulated address continuation
            record_text = line

            # Check if previous line (if it exists and has no $) is a continuation
            if i > 0:
                prev_line = lines[i - 1]
                if "$" not in prev_line and prev_line and not any(x in prev_line for x in ["Full Address", "CDOT :", "OBM :"]):
                    # It's likely a continuation of wrapped address
                    # Include it in the record
                    if len(prev_line) < 100:  # Reasonable length for address continuation
                        record_text = prev_line + " " + line
                        i -= 1  # We'll skip the prev line next iteration

            if current_ward and current_category:
                adapter = MenuAdapter2012 if 2012 <= year <= 2016 else MenuAdapter2017Plus

                try:
                    record = adapter.parse_row(record_text, current_ward, year, current_category)
                    if record:
                        records.append(record)
                except Exception:
                    pass

        i += 1

    return records


def extract_from_pdf_tables(
    tables: List[List[List]], year: int
) -> List[SpendingRecord]:
    """Extract spending records from pdfplumber table list.

    For 2012 format (table-based):
    - Headers: [Ward header], [Category header], [Column headers]
    - Data rows follow

    Returns list of SpendingRecord objects.
    """
    records = []
    current_ward = None
    current_category = None
    column_headers = None

    for table_idx, table in enumerate(tables):
        if not table:
            continue

        for row_idx, row in enumerate(table):
            if not row or not any(cell for cell in row):
                continue

            # Try to extract ward from row
            ward = extract_ward_from_table_row(row)
            if ward:
                current_ward = ward
                column_headers = None  # Reset headers
                continue

            # Try to extract category from row
            category = extract_category_from_table_row(row)
            if category and "Program" in str(row[0] or ""):
                current_category = category
                column_headers = None  # Reset headers
                continue

            # Check if this is a column header row
            if row[0] and "Address" in str(row[0]):
                column_headers = row
                continue

            # If we have all context, try to parse as data row
            if current_ward and current_category and column_headers:
                # Reconstruct text line from row
                text_line = " | ".join(str(cell).strip() for cell in row if cell)

                if "$" in text_line:  # Has a cost
                    adapter = MenuAdapter2012 if 2012 <= year <= 2016 else MenuAdapter2017Plus

                    try:
                        record = adapter.parse_row(text_line, current_ward, year)
                        if record:
                            records.append(record)
                    except Exception:
                        pass

    return records
