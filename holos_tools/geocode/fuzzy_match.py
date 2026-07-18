"""Fuzzy street matching using Levenshtein distance.

PHASE 2 ENHANCEMENT: Typo-tolerant street name matching for Stage 1/2 fallback.
When exact match fails, try fuzzy match with edit distance <= 2.

Algorithm: Levenshtein distance (edit distance)
- Counts minimum number of single-character edits (insert/delete/substitute)
- max_distance=2 catches most typos (e.g., "DIVSION" → "DIVISION")
- Performance: O(m*n) where m,n are string lengths; acceptable for <3000 streets

Examples:
- "DIVSION" → "DIVISION" (distance 1)
- "ADDERSON" → "ANDERSON" (distance 1)
- "DIV ST" → "DIVISION ST" (distance 3, too far; skip)
"""


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings.

    Returns minimum number of single-character edits needed to transform s1 → s2.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # j+1 instead of j since previous_row and current_row are one character longer than s2
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_fuzzy_match(query_street: str, reference_streets: list, max_distance: int = 2) -> tuple:
    """Find best fuzzy match for a street name from reference list.

    Args:
        query_street: Street name to match (e.g., "DIVSION")
        reference_streets: List of valid street names from database
        max_distance: Maximum edit distance to consider (default 2)

    Returns:
        (matched_street, distance) or (None, float('inf')) if no match within threshold
    """
    best_match = None
    best_distance = float('inf')

    for ref_street in reference_streets:
        distance = levenshtein_distance(query_street.upper(), ref_street.upper())
        if distance < best_distance and distance <= max_distance:
            best_distance = distance
            best_match = ref_street

    return best_match, best_distance


class FuzzyMatcher:
    """Street name fuzzy matching for geocoding fallback."""

    def __init__(self, reference_streets: list):
        """Initialize with a list of valid reference street names.

        Args:
            reference_streets: List of known valid street names from database
        """
        self.reference_streets = reference_streets
        self.street_upper = [s.upper() for s in reference_streets]

    def match(self, query_street: str, max_distance: int = 2) -> tuple:
        """Find best fuzzy match for query street.

        Returns:
            (matched_street, distance) or (None, inf) if no match
        """
        if not query_street:
            return None, float('inf')

        best_match = None
        best_distance = float('inf')

        query_upper = query_street.upper()
        for i, ref_street in enumerate(self.street_upper):
            distance = levenshtein_distance(query_upper, ref_street)
            if distance < best_distance and distance <= max_distance:
                best_distance = distance
                best_match = self.reference_streets[i]

        return best_match, best_distance
