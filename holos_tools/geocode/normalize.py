"""Step 3a: Normalize location text (PHASE 1 ENHANCED).

Runbook Step 3a: Unicode NFC, uppercase, USPS suffix expansion, abbreviation dicts.
Handles OCR noise in numeric tokens only (never street names yet).

PHASE 1 ENHANCEMENTS (2026-07-18):
- Directional prefix standardization (E→EAST, W→WEST, N→NORTH, S→SOUTH)
- Consistent title-case output for human readability
- Preserve FROM/TO syntax for range addresses
"""

import re
import unicodedata


USPS_SUFFIX_EXPANSIONS = {
    'ST': 'STREET',
    'AVE': 'AVENUE',
    'AV': 'AVENUE',
    'BLVD': 'BOULEVARD',
    'DR': 'DRIVE',
    'RD': 'ROAD',
    'LN': 'LANE',
    'CT': 'COURT',
    'PL': 'PLACE',
    'PK': 'PARK',
    'TERR': 'TERRACE',
    'PKWY': 'PARKWAY',
    'EXPY': 'EXPRESSWAY',
    'ROAD': 'ROAD',
    'DRIVE': 'DRIVE',
}

ABBREVIATION_EXPANSIONS = {
    'BLK': 'BLOCK',
    'BK': 'BLOCK',
    'BTW': 'BETWEEN',
    'BET': 'BETWEEN',
    'FRM': 'FROM',
    'FROM': 'FROM',
    'TO': 'TO',
}

# PHASE 1: Directional standardization (word-boundary safe)
DIRECTIONAL_EXPANSIONS = {
    'E': 'EAST',
    'W': 'WEST',
    'N': 'NORTH',
    'S': 'SOUTH',
    'NE': 'NORTHEAST',
    'NW': 'NORTHWEST',
    'SE': 'SOUTHEAST',
    'SW': 'SOUTHWEST',
}

# Directionals that should NOT be auto-expanded in normalize (let parser handle context)
DIRECTIONAL_PREFIXES = {'N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW'}

NUMERIC_REPAIR_MAP = {
    'O': '0',  # O (letter O) → 0 (zero)
    'I': '1',  # I (letter I) → 1 (one)
    'L': '1',  # L (letter L) → 1 (one)
    'Z': '2',  # Z (letter Z) → 2 (two)
    'S': '5',  # S (letter S) → 5 (five)
    'B': '8',  # B (letter B) → 8 (eight)
}


def normalize(text: str) -> str:
    """Normalize location text: Unicode NFC, uppercase, expand abbreviations.

    PHASE 1 (2026-07-18): Added directional standardization + title case.

    Args:
        text: Raw location text

    Returns:
        Normalized text (title-case, expanded abbreviations and directionals)
    """
    if not text:
        return ""

    # Step 1: Unicode normalization (NFC)
    text = unicodedata.normalize('NFC', text)

    # Step 2: Uppercase (intermediate; will title-case at end)
    text = text.upper().strip()

    # Step 3: Normalize whitespace (collapse multiple spaces)
    text = re.sub(r'\s+', ' ', text)

    # Step 3.5: Strip period-directionals (S., W., N., E.)
    text = re.sub(r'\b([NSEW])\.\s+', r'\1 ', text)

    # Step 4: Repair numeric tokens (OCR noise: O→0, I→1, S→5, B→8)
    def repair_numeric_token(match):
        token = match.group(0)
        if re.match(r'^\d+(ST|ND|RD|TH)$', token):
            return token
        if re.search(r'\d', token) and re.search(r'^[OILZB]', token):
            for bad, good in NUMERIC_REPAIR_MAP.items():
                token = token.replace(bad, good)
        return token

    text = re.sub(r'\d+[A-Z]*\d*|\d+', repair_numeric_token, text)

    # Step 5: Expand USPS suffix abbreviations (ST→STREET, AVE→AVENUE, etc.)
    for abbr, full in USPS_SUFFIX_EXPANSIONS.items():
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)

    # Step 6: Expand other abbreviations (BLK→BLOCK, FRM→FROM, etc.)
    for abbr, full in ABBREVIATION_EXPANSIONS.items():
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)

    # PHASE 1 ENHANCEMENT: Step 6.5 — Expand directional abbreviations (N→NORTH, E→EAST, etc)
    # But be careful: only expand if it's a standalone word, not part of "NEW" or other street names
    for abbr, full in DIRECTIONAL_EXPANSIONS.items():
        # Use word boundaries: \bN\b matches "N" but not "NEW"
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)

    # Step 7: Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)

    # PHASE 1 ENHANCEMENT: Step 7.5 — Convert to Title Case for consistency
    # This makes addresses human-readable and consistent with reference data
    text = _to_title_case(text)

    return text


def _to_title_case(text: str) -> str:
    """Convert text to title case, handling directionals and special words.

    Ensures "N" stays "N" but "NORTH CLARK" becomes "North Clark".
    Preserves FROM/TO in address ranges.
    """
    if not text:
        return ""

    words = text.split()
    result = []

    for word in words:
        # Don't title-case very short directional abbreviations that might be compass points
        if len(word) == 1 and word in 'NSEW':
            result.append(word)
        # Don't change words that are already all caps and short (like abbreviations)
        elif len(word) <= 2 and word.isupper():
            result.append(word)
        else:
            # Title case: capitalize first letter, lowercase rest
            result.append(word.capitalize())

    return ' '.join(result)
