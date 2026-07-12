"""Step 3a: Normalize location text.

Runbook Step 3a: Unicode NFC, uppercase, USPS suffix expansion, abbreviation dicts.
Handles OCR noise in numeric tokens only (never street names yet).
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
    'ROAD': 'ROAD',  # Already expanded
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
    # Note: Do NOT expand single-letter directionals here (N, S, E, W).
    # They're handled by the component parser, which has context.
    # Expanding them here would break street names that happen to start with these letters.
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

    Args:
        text: Raw location text

    Returns:
        Normalized text (uppercase, expanded abbreviations)
    """
    if not text:
        return ""

    # Step 1: Unicode normalization (NFC)
    text = unicodedata.normalize('NFC', text)

    # Step 2: Uppercase
    text = text.upper().strip()

    # Step 3: Normalize whitespace (collapse multiple spaces)
    text = re.sub(r'\s+', ' ', text)

    # Step 4: Repair numeric tokens (OCR noise: O→0, I→1, S→5, B→8)
    # Only repair inside tokens that look like numbers
    def repair_numeric_token(match):
        token = match.group(0)
        if re.search(r'\d', token):  # Only if it has digits
            for bad, good in NUMERIC_REPAIR_MAP.items():
                token = token.replace(bad, good)
        return token

    text = re.sub(r'\d+[A-Z]*\d*|\d+', repair_numeric_token, text)

    # Step 5: Expand USPS suffix abbreviations (ST→STREET, AVE→AVENUE, etc.)
    # Be careful not to expand directional prefixes
    for abbr, full in USPS_SUFFIX_EXPANSIONS.items():
        # Word boundary: ensure it's a standalone word (not part of a longer word)
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)

    # Step 6: Expand other abbreviations (BLK→BLOCK, FRM→FROM, etc.)
    # Directionals (N, S, E, W) are NOT expanded here; the component parser handles them
    # with proper context awareness
    for abbr, full in ABBREVIATION_EXPANSIONS.items():
        text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text)

    # Step 7: Clean up extra whitespace again
    text = re.sub(r'\s+', ' ', text)

    return text
