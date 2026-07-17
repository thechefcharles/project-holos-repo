"""Step 3c: Component parsing (extract address parts).

Runbook Step 3c: parse normalized address into number, predir, street, suffix using
CRF-based tagger (usaddress library). Falls back to simple regex if usaddress fails.
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict

try:
    import usaddress
    HAS_USADDRESS = True
except ImportError:
    HAS_USADDRESS = False


@dataclass
class AddressComponents:
    """Parsed address components."""
    number: Optional[str] = None  # "123"
    predir: Optional[str] = None  # "N", "NORTH"
    street: Optional[str] = None  # "MICHIGAN"
    suffix: Optional[str] = None  # "AVE", "AVENUE"
    postdir: Optional[str] = None  # "NORTH" (post-directional, rare)
    confidence: float = 0.0  # 0-1, indicates parsing confidence


class AddressParser:
    """Parse normalized address into components (number, predir, street, suffix)."""

    DIRECTIONALS = {
        'N': 'NORTH', 'NORTH': 'NORTH',
        'S': 'SOUTH', 'SOUTH': 'SOUTH',
        'E': 'EAST', 'EAST': 'EAST',
        'W': 'WEST', 'WEST': 'WEST',
        'NE': 'NORTHEAST', 'NORTHEAST': 'NORTHEAST',
        'NW': 'NORTHWEST', 'NORTHWEST': 'NORTHWEST',
        'SE': 'SOUTHEAST', 'SOUTHEAST': 'SOUTHEAST',
        'SW': 'SOUTHWEST', 'SOUTHWEST': 'SOUTHWEST',
    }

    STREET_SUFFIXES = {
        'STREET', 'ST', 'AVENUE', 'AVE', 'AV',
        'BOULEVARD', 'BLVD', 'DRIVE', 'DR',
        'ROAD', 'RD', 'LANE', 'LN', 'COURT', 'CT',
        'PLACE', 'PL', 'PARK', 'PK', 'SQUARE', 'SQ',
        'TERRACE', 'TERR', 'TRAIL', 'PARKWAY', 'PKWY',
    }

    @classmethod
    def _normalize_address_range(cls, location_text: str) -> str:
        """Convert address ranges to midpoint.

        Examples:
          "2100-2200 N MAIN ST" -> "2150 N MAIN ST"
          "100-200 MICHIGAN AVE" -> "150 MICHIGAN AVE"

        Returns the original text if no range is detected.
        """
        # Pattern: number-number at start of string
        range_match = re.match(r'^(\d+)-(\d+)\s+(.+)$', location_text.strip())
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            rest = range_match.group(3)
            midpoint = (start + end) // 2
            return f"{midpoint} {rest}"
        return location_text

    @classmethod
    def parse(cls, location_text: str) -> AddressComponents:
        """Parse address into components.

        Args:
            location_text: Normalized (uppercased, expanded abbreviations) address text

        Returns:
            AddressComponents with extracted fields and confidence score
        """
        if not location_text:
            return AddressComponents(confidence=0.0)

        # Preprocess: split on semicolon and take first part (primary address)
        # e.g., "6150 W FLETCHER; 6144-6156 W FLETCHER" -> "6150 W FLETCHER"
        text_to_parse = location_text.split(';')[0].strip()

        # Handle address ranges: "2100-2200 N MAIN ST" -> "2150 N MAIN ST" (midpoint)
        text_to_parse = cls._normalize_address_range(text_to_parse)

        # Try usaddress library first (if available)
        if HAS_USADDRESS:
            result = cls._parse_with_usaddress(text_to_parse)
            if result.number or result.street:  # At least some components parsed
                return result

        # Fallback: simple regex parser
        return cls._parse_with_regex(text_to_parse)

    @classmethod
    def _parse_with_usaddress(cls, text: str) -> AddressComponents:
        """Parse using usaddress CRF tagger."""
        try:
            tagged = usaddress.tag(text)
            # usaddress returns list of (token, label) tuples
            components = AddressComponents()

            for token, label in tagged:
                if label == 'AddressNumber':
                    components.number = token
                elif label == 'StreetNamePreDirectional':
                    components.predir = cls.DIRECTIONALS.get(token, token)
                elif label == 'StreetName':
                    components.street = token
                elif label == 'StreetNamePostType':
                    components.suffix = token

            components.confidence = 0.92 if components.street else 0.60
            return components

        except Exception:
            # usaddress throws on unparseable text; fall through to regex
            return AddressComponents(confidence=0.0)

    @classmethod
    def _parse_with_regex(cls, text: str) -> AddressComponents:
        """Parse using simple regex patterns (fallback)."""
        components = AddressComponents()
        parts = text.split()

        if not parts:
            return components

        idx = 0

        # Extract number (must be first)
        if parts[idx].isdigit():
            components.number = parts[idx]
            idx += 1

        # Extract pre-directional (if present)
        if idx < len(parts) and parts[idx] in cls.DIRECTIONALS:
            components.predir = cls.DIRECTIONALS[parts[idx]]
            idx += 1

        # Remaining parts: street name + optional suffix
        if idx < len(parts):
            remaining = ' '.join(parts[idx:])

            # Try to extract suffix (suffix usually at the end)
            for suffix in cls.STREET_SUFFIXES:
                if remaining.endswith(suffix):
                    components.suffix = suffix
                    components.street = remaining[:-(len(suffix))].strip()
                    break

            # If no suffix found, whole remaining is street
            if not components.street:
                components.street = remaining

        # Confidence: number + street = high; just street = medium
        if components.number and components.street:
            components.confidence = 0.90
        elif components.street:
            components.confidence = 0.70
        else:
            components.confidence = 0.30

        return components
