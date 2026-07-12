"""Step 3b: Grammar classification (location type detection).

Runbook Step 3b: detect which type of location text we're dealing with (single_address,
street_segment, hundred_block, intersection, etc.) so the cascade knows which stages apply.

Two-layer approach:
- Layer 1 (80%): regex rules, deterministic and fast
- Layer 2 (20%): Claude API for ambiguous/edge cases (with structured output schema)
"""

import re
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class GrammarClassification:
    """Result of grammar classification."""
    grammar: str  # single_address, street_segment, etc.
    confidence: float  # 0.0–1.0
    method: str  # "regex" or "llm"
    repairs: list = None  # [{'original': 'x', 'suggestion': 'y'}, ...]


class GrammarClassifier:
    """Classify location text into grammar types (regex layer only for Phase 1B)."""

    # Regex patterns for deterministic classification
    PATTERNS = {
        'wardwide': [
            r'\bWARD\s*[-–]?\s*WIDE\b',
            r'\bENTIRE\s+WARD\b',
            r'\bALL\s+WARDS\b',
            r'\bVARIOUS\s+LOCATIONS?\b',  # "various locations" indicates wardwide
        ],
        'street_segment': [
            r'ON\s+\w+.*FROM\s+\w+.*TO\s+\w+',  # ON X FROM Y TO Z (with parens allowed)
            r'FROM\s+[NSEW]?\s+\w+.*TO\s+[NSEW]?\s+\w+',  # FROM X TO Y (implicit street)
            r'BETWEEN\s+\w+\s+AND\s+\w+',  # BETWEEN X AND Y
            r'--.*-TO-',  # Double-dash with "-to-": "ST1-- --ST2 (num) -to- ST3"
            r'-TO-',  # "-to-" separator (variant of TO)
        ],
        'hundred_block': [
            r'\d+\s*BL?K\b',  # 5400 BLK or 5400 BK
            r'\d+\s*BLOCK\b',  # 5400 BLOCK
        ],
        'address_range': [
            # Format: "ADDRESS1; ADDRESS-RANGE" (semicolon-separated in data)
            r';\s*\d+\s*[-–]\s*\d+',
            # Format: "5800-5999 W STREET" (direct range at start)
            r'^\d+\s*[-–]\s*\d+\s+[NSEW]?\s+(STREET|AVENUE|BLVD|AVE|DRIVE|RD|ROAD|LANE|LN|CT|COURT|ST|PLACE|PL)',
        ],
        'intersection': [
            r'\w+\s+&\s+\w+',  # X & Y
            r'\bNEAR\b',  # X NEAR Y
            r'\bAT\b',  # X AT Y
        ],
        'alley_block_polygon': [
            r'--.*--',  # Double-dash format: "ST1--ST2--AVE1--AVE2" (bounded block)
            r'\bALLEY\b',  # Alley as explicit marker
            r'\bALLEYS\b',
        ],
        'named_place': [
            r'\b(PARK|PLAZA|LIBRARY|SCHOOL|BEACH|BRIDGE|GARDEN|MONUMENT|MUSEUM|CENTER|FIELD|COURT|PLAZA)\b',
        ],
        'multi_location': [
            r'\s&\s.*\s&\s',  # Multiple & (X & Y & Z) — but NOT "ST & AVE" (intersection)
        ],
    }

    @classmethod
    def classify(cls, location_text: str, ward: Optional[str] = None) -> GrammarClassification:
        """Classify location text into a grammar type (regex layer, Phase 1B)."""
        if not location_text:
            return GrammarClassification('unresolvable_text', 0.0, 'regex')

        text = location_text.upper().strip()
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace

        # Order matters: more specific patterns first
        # Wardwide must come before everything (catches "various locations" too)
        if any(re.search(p, text) for p in cls.PATTERNS.get('wardwide', [])):
            return GrammarClassification('wardwide', 0.95, 'regex')

        # Street segment: ON/FROM/TO/BETWEEN patterns (catches ranges with parens)
        if any(re.search(p, text) for p in cls.PATTERNS.get('street_segment', [])):
            return GrammarClassification('street_segment', 0.95, 'regex')

        # Hundred block: strict pattern
        if any(re.search(p, text) for p in cls.PATTERNS.get('hundred_block', [])):
            return GrammarClassification('hundred_block', 0.95, 'regex')

        # Alley block polygon: double-dash format (blocks bounded by streets)
        # Must come before multi_location (which also has &)
        if any(re.search(p, text) for p in cls.PATTERNS.get('alley_block_polygon', [])):
            # But exclude if it looks like a multi-location address (has comma, semicolon + number)
            if not re.search(r'[;,]\s*\d+', text):
                return GrammarClassification('alley_block_polygon', 0.90, 'regex')

        # Multi-location: multiple & (street1 & street2 & avenue1 & avenue2 type patterns)
        # or semicolon separating full addresses
        if cls._is_multi_location(text):
            return GrammarClassification('multi_location', 0.90, 'regex')

        # Address range: ranges can be at start or after semicolon
        if cls._is_address_range(text):
            return GrammarClassification('address_range', 0.90, 'regex')

        # Intersection: X & Y or X NEAR Y (but not alley_block or multi_location)
        if any(re.search(p, text) for p in cls.PATTERNS.get('intersection', [])):
            # Validate it looks like streets, not full addresses
            if re.search(r'[NSEW]\s+\w+|STREET|AVENUE|AVE|BLVD', text):
                return GrammarClassification('intersection', 0.85, 'regex')

        # Named place: park, plaza, library, etc.
        if any(re.search(p, text) for p in cls.PATTERNS.get('named_place', [])):
            # Must NOT be a street address
            if not re.match(r'^\d+', text):
                return GrammarClassification('named_place', 0.95, 'regex')

        # Single address: number + optional direction + street name (most forgiving for OCR)
        if cls._is_single_address(text):
            return GrammarClassification('single_address', 0.92, 'regex')

        # Fallback to unresolvable
        return GrammarClassification('unresolvable_text', 0.3, 'regex')

    @classmethod
    def _is_single_address(cls, text: str) -> bool:
        """Check if text looks like a single address (number + street)."""
        # Pattern: digit, optional direction, street name, optional suffix
        # Forgiving on street suffix (catches abbreviated/OCR-corrupted)
        if re.match(r'^\d+\s+[NSEW]?\s*\w+', text):
            # Has a street-type word (abbreviated or full)
            if re.search(r'(ST|AVE|BLVD|RD|STREET|AVENUE|DRIVE|ROAD|LANE|LN|CT|COURT|PLACE|PL|DR|AV|BV)', text):
                return True
        return False

    @classmethod
    def _is_address_range(cls, text: str) -> bool:
        """Check if text is an address range (1200-1298 W STREET or 1200-1298 W STREET; ...)."""
        # Direct range: "1200-1298 W STREET"
        if re.match(r'^\d+\s*[-–]\s*\d+\s+[NSEW]?\s*\w+', text):
            return True
        # Range after semicolon: "6150 W FLETCHER; 6144-6156 W FLETCHER"
        if re.search(r';\s*\d+\s*[-–]\s*\d+\s*[NSEW]?', text):
            return True
        return False

    @classmethod
    def _is_multi_location(cls, text: str) -> bool:
        """Check if text is multiple locations (addresses joined by & or ;)."""
        ampersand_count = text.count('&')

        # Two & with coordinates in both parts: "4500 N LINCOLN & 1940 S DESPLAINES" = multi_location
        if ampersand_count == 2:
            parts = text.split('&')
            if len(parts) == 3:  # Two ampersands = 3 parts
                # Check if BOTH outer parts have coordinates (number + direction/street)
                has_coords = [bool(re.search(r'\d+\s+[NSEW]', part.strip())) for part in [parts[0], parts[2]]]
                if all(has_coords):
                    return True

        # Multiple & (4+ streets): "ST1 & ST2 & ST3 & ST4" = alley_block (handled separately)
        # But "ADDR1 & ADDR2 & ADDR3" = multi_location
        if ampersand_count >= 3:
            parts = [p.strip() for p in text.split('&')]
            # If MOST parts have coordinates, it's multi-location of addresses
            coords_count = sum(1 for p in parts if re.search(r'\d+\s+[NSEW]', p))
            if coords_count >= len(parts) * 0.5:  # At least half have coordinates
                return True

        # Semicolon-separated different addresses (not a range or alley)
        if ';' in text and ampersand_count <= 1:
            # If it's "ADDR1; ADDR2" (not "ADDR1; RANGE"), it's multi-location
            if not re.search(r';\s*\d+\s*[-–]', text):
                parts = text.split(';')
                if len(parts) >= 2:
                    # Check if both parts look like addresses (have coordinates)
                    if all(re.search(r'\d+', part) for part in parts):
                        return True

        return False


# For Phase 1B, Claude API layer is stubbed (added in Phase 2)
# This is where ambiguous cases would go to Claude for structured disambiguation
def classify_with_llm(location_text: str, ward: str, year: str) -> GrammarClassification:
    """Classify using Claude API (Phase 2; stubbed for Phase 1B)."""
    # Placeholder: in Phase 2, this would call Claude with structured output schema
    # For Phase 1B, fall back to regex
    return GrammarClassifier.classify(location_text, ward)
