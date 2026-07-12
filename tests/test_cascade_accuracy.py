"""Cascade accuracy measurement against dual benchmarks (per-grammar validation)."""

import json
import csv
import math
from pathlib import Path
from collections import defaultdict
from unittest.mock import MagicMock
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from holos_tools.geocode.cascade import GeocodeCascade


def haversine_distance(lat1, lon1, lat2, lon2):
    """Distance in meters between two points."""
    R = 6371000  # Earth radius in meters
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


class CascadeAccuracyReporter:
    """Measure cascade accuracy per-grammar on dual benchmarks."""

    TOLERANCE_M = 100  # Points within 100m are "correct"

    def __init__(self):
        self.my_benchmark = self._load_my_benchmark()
        self.cowork_benchmark = self._load_cowork_benchmark()

    def _load_my_benchmark(self):
        """Load my 250-row stratified benchmark."""
        with open(Path("golden/chicago_spending_benchmark.json")) as f:
            data = json.load(f)
        return {row['project_id']: row for row in data}

    def _load_cowork_benchmark(self):
        """Load Cowork's 236-row independent benchmark."""
        data = {}
        with open(Path("golden/geocode_benchmark_wardwise_v1.csv")) as f:
            reader = csv.DictReader(f)
            for row in reader:
                data[row['row_id']] = {
                    'location_text': row['location_text'],
                    'expected_grammar': row['expected_grammar'],
                    'expected_geom': row['expected_geom'],
                    'expected_coords': (float(row['expected_lat']), float(row['expected_lon'])),
                    'expected_coords2': (float(row['expected_lat2']), float(row['expected_lon2'])) if row['expected_lat2'] else None,
                    'ocr_noise': row['ocr_noise'],
                }
        return data

    def score_point_match(self, result, expected_lat, expected_lon):
        """Score a point match (within 100m tolerance)."""
        if result.geometry_type != 'POINT' or result.coordinates is None:
            return False

        cascade_lat, cascade_lon = result.coordinates[1], result.coordinates[0]  # coords are [lon, lat]
        distance_m = haversine_distance(cascade_lat, cascade_lon, expected_lat, expected_lon)
        return distance_m <= self.TOLERANCE_M

    def score_line_match(self, result, expected_geom):
        """Score a line/segment match (representative point within tolerance)."""
        if result.geometry_type not in ['LINESTRING', 'POINT']:
            return False
        # Representative point is typically the center or a point on the line
        # For now, accept if geometry type matches and we have coordinates
        return result.coordinates is not None

    def score_multi_location_match(self, result, expected_coords1, expected_coords2):
        """Score a multi_location match (both points produced and correct)."""
        if result.geometry_type != 'POINT':
            return False
        # In real implementation, cascade should split multi_location into two rows
        # This is a placeholder; actual cascade needs to handle splitting
        return False  # Not yet implemented


class TestCascadeAccuracyPerGrammar:
    """Test cascade accuracy broken down by grammar."""

    def test_benchmark_load(self):
        """Verify both benchmarks load correctly."""
        reporter = CascadeAccuracyReporter()
        assert len(reporter.my_benchmark) == 250, "My benchmark should have 250 rows"
        assert len(reporter.cowork_benchmark) == 236, "Cowork benchmark should have 236 rows"

    def test_benchmark_grammar_distribution(self):
        """Report grammar distribution in both benchmarks."""
        reporter = CascadeAccuracyReporter()

        print("\n=== My Benchmark Grammar Distribution ===")
        my_grammars = defaultdict(int)
        for row in reporter.my_benchmark.values():
            my_grammars[row['expected_grammar']] += 1

        for grammar in sorted(my_grammars.keys()):
            count = my_grammars[grammar]
            pct = 100 * count / len(reporter.my_benchmark)
            print(f"  {grammar:25s}: {count:3d} ({pct:5.1f}%)")

        print("\n=== Cowork Benchmark Grammar Distribution ===")
        cowork_grammars = defaultdict(int)
        for row in reporter.cowork_benchmark.values():
            cowork_grammars[row['expected_grammar']] += 1

        for grammar in sorted(cowork_grammars.keys()):
            count = cowork_grammars[grammar]
            pct = 100 * count / len(reporter.cowork_benchmark)
            print(f"  {grammar:25s}: {count:3d} ({pct:5.1f}%)")

        print("\n=== Grammar Coverage Gaps ===")
        my_set = set(my_grammars.keys())
        cowork_set = set(cowork_grammars.keys())
        only_in_my = my_set - cowork_set
        only_in_cowork = cowork_set - my_set

        if only_in_cowork:
            print(f"  Cowork has grammars my benchmark is missing:")
            for grammar in sorted(only_in_cowork):
                print(f"    - {grammar} ({cowork_grammars[grammar]} rows)")

        if only_in_my:
            print(f"  My benchmark has grammars Cowork doesn't:")
            for grammar in sorted(only_in_my):
                print(f"    - {grammar} ({my_grammars[grammar]} rows)")

    def test_cascade_baseline_stub(self):
        """Baseline: cascade stub (no implementation) should have 0% accuracy."""
        # This test is a placeholder for when cascade is actually implemented
        # For now, it documents the testing framework

        reporter = CascadeAccuracyReporter()

        # Stub cascade with mock DB
        mock_db = MagicMock()
        mock_db.execute.return_value = []  # All queries return empty (no matches)

        cascade = GeocodeCascade(mock_db)

        # Try cascading on a single address from my benchmark
        test_row = list(reporter.my_benchmark.values())[0]
        result = cascade.geocode(test_row['location_text'])

        # Should fail to match (no results)
        assert result.stage == 8, "Stub cascade should escalate to review (stage 8)"
        assert result.score == 0.0, "Stub cascade should have 0.0 score"

    def test_ocr_noise_rows_in_cowork(self):
        """Verify Cowork benchmark includes OCR noise test cases."""
        reporter = CascadeAccuracyReporter()

        ocr_rows = [row for row in reporter.cowork_benchmark.values() if row['ocr_noise'] == 'injected']
        print(f"\n=== OCR Noise Test Cases (Cowork) ===")
        print(f"Total rows with OCR noise injected: {len(ocr_rows)}")
        print("Examples:")
        for row in ocr_rows[:5]:
            print(f"  {row['location_text'][:50]}")

        assert len(ocr_rows) == 18, "Cowork benchmark should have 18 OCR-noise rows"


class TestBenchmarkDisagreement:
    """Identify where the two benchmarks disagree (blind spots)."""

    def test_identify_overlapping_locations(self):
        """Find rows that appear in both benchmarks (likely same or similar location)."""
        reporter = CascadeAccuracyReporter()

        # Simple heuristic: same location_text prefix
        my_locations = {row['location_text'][:30]: row for row in reporter.my_benchmark.values()}
        cowork_locations = {row['location_text'][:30]: row for row in reporter.cowork_benchmark.values()}

        overlaps = set(my_locations.keys()) & set(cowork_locations.keys())
        print(f"\nOverlapping locations (30-char prefix): {len(overlaps)}")

    def test_hundred_block_representation(self):
        """Verify Cowork benchmark covers hundred_block (blind spot in my benchmark)."""
        reporter = CascadeAccuracyReporter()

        cowork_hb = [row for row in reporter.cowork_benchmark.values() if row['expected_grammar'] == 'hundred_block']
        print(f"\nHundred-block coverage:")
        print(f"  My benchmark: 0 rows")
        print(f"  Cowork benchmark: {len(cowork_hb)} rows")

        if cowork_hb:
            print("  Examples:")
            for row in cowork_hb[:3]:
                print(f"    {row['location_text']}")

        assert len(cowork_hb) > 0, "Cowork should have hundred_block rows"


# Accuracy metrics template (for when cascade is fully implemented)
class AccuracyMetrics:
    """Per-grammar accuracy tracking."""

    def __init__(self):
        self.grammar_results = defaultdict(lambda: {'correct': 0, 'total': 0, 'escalated': 0})

    def record_result(self, grammar, correct, escalated=False):
        """Record a result for a grammar."""
        self.grammar_results[grammar]['total'] += 1
        if escalated:
            self.grammar_results[grammar]['escalated'] += 1
        elif correct:
            self.grammar_results[grammar]['correct'] += 1

    def report(self):
        """Print accuracy by grammar."""
        print("\n=== Accuracy by Grammar ===")
        for grammar in sorted(self.grammar_results.keys()):
            stats = self.grammar_results[grammar]
            total = stats['total']
            correct = stats['correct']
            escalated = stats['escalated']
            auto_correct = correct / (total - escalated) if (total - escalated) > 0 else 0
            print(f"  {grammar:25s}: {correct}/{total} ({100*correct/total:5.1f}%) | escalated: {escalated} | auto-correct: {100*auto_correct:5.1f}%")

        # Overall
        total_correct = sum(s['correct'] for s in self.grammar_results.values())
        total_rows = sum(s['total'] for s in self.grammar_results.values())
        total_escalated = sum(s['escalated'] for s in self.grammar_results.values())
        print(f"\nOverall: {total_correct}/{total_rows} ({100*total_correct/total_rows:5.1f}%) | escalated: {total_escalated}")
