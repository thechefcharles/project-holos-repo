#!/usr/bin/env python3
"""Manual review workflow for truncated addresses (Tier 2 Part 3).

Identifies records flagged with is_truncated=True and provides:
1. Review interface (CLI or JSON for dashboard integration)
2. Automatic recovery heuristics (fuzzy partial matching)
3. Audit trail (decisions logged for reproducibility)

Usage:
  # Review truncated records:
  uv run python holos_tools/extract/review_truncated.py --input 2017_valid_records.json

  # Auto-recover with fuzzy matching:
  uv run python holos_tools/extract/review_truncated.py --input 2017_valid_records.json \
    --auto-recover --output recovered.json

  # Export review queue for dashboard:
  uv run python holos_tools/extract/review_truncated.py --input 2017_valid_records.json \
    --export-queue review_queue.json
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import re
from difflib import SequenceMatcher


@dataclass
class TruncatedRecord:
    """A record flagged as truncated."""
    ward: int
    year: int
    category: str
    location: str
    cost: float
    is_truncated: bool
    missing_part: Optional[str] = None  # What we think is missing
    confidence: float = 0.0  # Confidence in recovery (0-1)
    recovered_location: Optional[str] = None  # Attempted recovery
    human_review_needed: bool = True


class TruncationRecovery:
    """Heuristics to recover truncated address information."""

    # Known Chicago street endings that commonly follow directionals
    COMMON_STREETS = {
        "N": ["MICHIGAN", "CLARK", "STATE", "DEARBORN", "LASALLE", "WELLS", "WABASH"],
        "S": ["MICHIGAN", "CLARK", "STATE", "HALSTED", "COTTAGE GROVE", "ELLIS"],
        "E": ["CHICAGO", "OHIO", "ONTARIO", "SUPERIOR", "HURON", "ERIE"],
        "W": ["CHICAGO", "OHIO", "CONGRESS", "HARRISON", "POLK", "TAYLOR"],
    }

    @staticmethod
    def extract_bare_directional(location: str) -> Optional[Tuple[str, str]]:
        """Extract bare directional and context before it.

        Returns: (context_before, bare_directional)
        Example: "ON STREET FROM 1ST TO W" -> ("ON STREET FROM 1ST TO", "W")
        """
        match = re.search(r'((?:FROM|TO|&)\s+)([NSEW])(?:\s|$)', location)
        if match:
            context = location[:match.end(1) + len(match.group(1)) - 1].strip()
            directional = match.group(2)
            return (context, directional)
        return None

    @classmethod
    def suggest_recovery(cls, location: str) -> List[Tuple[str, float]]:
        """Suggest recovered addresses with confidence scores.

        Returns: List of (recovered_location, confidence) tuples
        """
        result = cls.extract_bare_directional(location)
        if not result:
            return []

        context, bare_dir = result
        suggestions = []

        # Suggest common streets for this directional
        if bare_dir in cls.COMMON_STREETS:
            for street in cls.COMMON_STREETS[bare_dir]:
                recovered = f"{context} {bare_dir} {street}"
                # Confidence based on:
                # - Directional match (high)
                # - Street frequency in Chicago (medium)
                confidence = 0.65  # Conservative estimate
                suggestions.append((recovered, confidence))

        return sorted(suggestions, key=lambda x: -x[1])

    @staticmethod
    def score_recovery_confidence(original: str, recovered: str) -> float:
        """Score how likely the recovery is correct (0-1)."""
        # Simple heuristic: longer matches = higher confidence
        matcher = SequenceMatcher(None, original, recovered)
        ratio = matcher.ratio()
        # Boost confidence if recovered ends with a street type
        if re.search(r'(?:ST|AVE|BLVD|RD|PKWY)\s*$', recovered, re.IGNORECASE):
            ratio += 0.1
        return min(ratio, 1.0)


class ReviewQueue:
    """Manages the manual review workflow."""

    def __init__(self, truncated_records: List[TruncatedRecord]):
        self.records = truncated_records
        self.reviewed = []
        self.approved = []
        self.rejected = []

    def load_from_json(self, input_file: str) -> int:
        """Load truncated records from JSON export of 2017 data."""
        with open(input_file) as f:
            data = json.load(f)

        count = 0
        for record in data:
            result = record.get('result', {})
            location = record.get('record', {}).get('location', '')

            if result.get('method') == 'none' and 'FROM' in location.upper() and 'TO' in location.upper():
                # Check if it matches truncation pattern
                if re.search(r'(?:FROM|TO|&)\s+[NSEW]\s*$', location):
                    tr = TruncatedRecord(
                        ward=record.get('record', {}).get('ward', 0),
                        year=record.get('record', {}).get('year', 2017),
                        category=record.get('record', {}).get('category', 'Unknown'),
                        location=location,
                        cost=record.get('record', {}).get('cost', 0),
                        is_truncated=True,
                    )

                    # Try automatic recovery
                    suggestions = TruncationRecovery.suggest_recovery(location)
                    if suggestions:
                        tr.recovered_location = suggestions[0][0]
                        tr.confidence = suggestions[0][1]

                    self.records.append(tr)
                    count += 1

        return count

    def approve_recovery(self, record: TruncatedRecord, recovered_location: str):
        """User approves a recovery suggestion."""
        record.recovered_location = recovered_location
        record.human_review_needed = False
        self.approved.append(record)

    def reject_recovery(self, record: TruncatedRecord):
        """User rejects all recovery suggestions."""
        record.human_review_needed = True
        self.rejected.append(record)

    def export_review_queue(self, output_file: str) -> int:
        """Export queue for dashboard UI review."""
        queue = [
            {
                **asdict(r),
                "suggestions": TruncationRecovery.suggest_recovery(r.location),
            }
            for r in self.records
        ]

        with open(output_file, 'w') as f:
            json.dump(queue, f, indent=2)

        return len(queue)

    def export_recovered(self, output_file: str) -> int:
        """Export records with successful recoveries."""
        recovered = [asdict(r) for r in self.approved if r.recovered_location]

        with open(output_file, 'w') as f:
            json.dump(recovered, f, indent=2)

        return len(recovered)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Manual review workflow for truncated addresses")
    parser.add_argument("--input", required=True, help="2017_valid_records.json or geocoded JSON")
    parser.add_argument("--export-queue", help="Export review queue to JSON (for dashboard)")
    parser.add_argument("--auto-recover", action="store_true", help="Auto-recover with fuzzy matching")
    parser.add_argument("--output", help="Output file for recovered records")
    args = parser.parse_args()

    # Load records
    queue = ReviewQueue([])
    count = queue.load_from_json(args.input)

    print(f"\n📋 Truncated Records Review Queue")
    print(f"   Total truncated records found: {count}")
    print(f"   Ready for manual review: {len(queue.records)}")

    if not queue.records:
        print("   ✅ No truncated records found")
        return

    # Show examples
    print(f"\n📌 Examples of truncated records:")
    for i, record in enumerate(queue.records[:3]):
        print(f"\n   {i+1}. Original location: '{record.location}'")
        if record.recovered_location:
            print(f"      Suggested recovery: '{record.recovered_location}'")
            print(f"      Confidence: {record.confidence:.1%}")
        print(f"      Category: {record.category} | Cost: ${record.cost:,.0f}")

    # Export queue for dashboard
    if args.export_queue:
        exported = queue.export_review_queue(args.export_queue)
        print(f"\n✅ Review queue exported to {args.export_queue}")
        print(f"   {exported} records with suggestions ready for dashboard review")

    # Auto-recover if requested
    if args.auto_recover:
        auto_approved = 0
        for record in queue.records:
            if record.confidence > 0.70:  # High confidence threshold
                queue.approve_recovery(record, record.recovered_location)
                auto_approved += 1

        print(f"\n✅ Auto-recovery complete")
        print(f"   High-confidence recoveries: {auto_approved}/{len(queue.records)}")

        if args.output:
            exported = queue.export_recovered(args.output)
            print(f"   Exported {exported} recovered records to {args.output}")

    print(f"\n💡 Next step: Review dashboard queue and approve/reject suggestions")
    print(f"   Or run with --auto-recover to auto-approve high-confidence suggestions (>70%)")


if __name__ == "__main__":
    main()
