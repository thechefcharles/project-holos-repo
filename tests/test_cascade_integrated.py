"""Integrated cascade tests: parse pipeline + matching stages + dual-benchmark accuracy.

Runs cascade end-to-end with mocked reference data against both benchmarks.
Measures per-grammar accuracy to identify which stages need work.
"""

import json
import csv
import math
from pathlib import Path
from collections import defaultdict
from unittest.mock import MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from holos_tools.geocode.grammar import GrammarClassifier
from holos_tools.geocode.normalize import normalize
from holos_tools.geocode.parser import AddressParser
from holos_tools.geocode.cascade import GeocodeCascade, GeocodeResult


class MockHolosDB:
    """Mock database with sample reference data (centerlines, wards, gazetteer)."""

    # Sample Chicago reference data
    CENTERLINES = [
        {'street_name': 'MICHIGAN', 'segment_id': 1, 'geom': 'LINESTRING(-87.6244 41.8709, -87.6244 41.8909)'},
        {'street_name': 'STATE', 'segment_id': 2, 'geom': 'LINESTRING(-87.6277 41.8709, -87.6277 41.8909)'},
        {'street_name': 'CLARK', 'segment_id': 3, 'geom': 'LINESTRING(-87.6310 41.8709, -87.6310 41.9009)'},
        {'street_name': 'DEARBORN', 'segment_id': 4, 'geom': 'LINESTRING(-87.6295 41.8709, -87.6295 41.8909)'},
        {'street_name': 'MADISON', 'segment_id': 5, 'geom': 'LINESTRING(-87.6244 41.8827, -87.6310 41.8827)'},
        {'street_name': 'DIVISION', 'segment_id': 6, 'geom': 'LINESTRING(-87.6680 41.9037, -87.6244 41.9037)'},
        {'street_name': 'WESTERN', 'segment_id': 7, 'geom': 'LINESTRING(-87.6881 41.8800, -87.6881 41.9200)'},
    ]

    WARDS = [
        {'ward_id': '32', 'geometry': 'POLYGON((-87.64 41.87, -87.61 41.87, -87.61 41.90, -87.64 41.90, -87.64 41.87))'},
        {'ward_id': '11', 'geometry': 'POLYGON((-87.64 41.90, -87.61 41.90, -87.61 41.93, -87.64 41.93, -87.64 41.90))'},
        {'ward_id': '4', 'geometry': 'POLYGON((-87.62 41.80, -87.59 41.80, -87.59 41.83, -87.62 41.83, -87.62 41.80))'},
        {'ward_id': '25', 'geometry': 'POLYGON((-87.71 41.91, -87.68 41.91, -87.68 41.94, -87.71 41.94, -87.71 41.91))'},
    ]

    GAZETTEER = [
        {'name': 'MILLENNIUM PARK', 'geometry': 'POLYGON((-87.6267 41.8827, -87.6220 41.8827, -87.6220 41.8856, -87.6267 41.8856, -87.6267 41.8827))'},
        {'name': 'GRANT PARK', 'geometry': 'POLYGON((-87.6220 41.8700, -87.6150 41.8700, -87.6150 41.8900, -87.6220 41.8900, -87.6220 41.8700))'},
    ]

    ADDRESS_POINTS = [
        {'number': 123, 'street': 'MICHIGAN', 'lon': -87.6244, 'lat': 41.8841},
        {'number': 456, 'street': 'STATE', 'lon': -87.6277, 'lat': 41.8841},
        {'number': 2345, 'street': 'CLARK', 'lon': -87.6310, 'lat': 41.8859},
        {'number': 5432, 'street': 'MADISON', 'lon': -87.6275, 'lat': 41.8827},
    ]

    def execute(self, sql, params=None):
        """Mock execute: return reference data based on query."""
        if 'address_points' in sql:
            # Address point exact match
            if 'WHERE' in sql:
                # Extract number and street from params
                num = params.get('address_number') if params else None
                street = params.get('street_name', '').upper() if params else ''

                for ap in self.ADDRESS_POINTS:
                    if ap['number'] == num and ap['street'].upper() == street.upper():
                        return [{'lon': ap['lon'], 'lat': ap['lat']}]
            return []

        if 'centerlines' in sql and 'from_house_num' in sql:
            # Centerline interpolation
            if 'WHERE' in sql and params:
                street = params.get('street_name', '').upper()
                for cl in self.CENTERLINES:
                    if cl['street_name'].upper() == street.upper():
                        return [{
                            'segment_id': cl['segment_id'],
                            'geom': cl['geom'],
                            'from_house_num_l': 100,
                            'to_house_num_l': 200,
                            'from_house_num_r': 101,
                            'to_house_num_r': 201,
                            'start_lon': -87.62,
                            'start_lat': 41.87,
                            'end_lon': -87.63,
                            'end_lat': 41.89,
                        }]
            return []

        if 'gazetteer' in sql:
            # Gazetteer lookup
            if 'WHERE' in sql:
                name = params.get('name', '').upper() if params else ''
                for gz in self.GAZETTEER:
                    if gz['name'].upper().startswith(name.upper()):
                        return [{'geom': gz['geometry'], 'lon': -87.6243, 'lat': 41.8841, 'name': gz['name']}]
            return []

        return []


class TestCascadeIntegrated:
    """Integrated cascade tests with parse pipeline + mock database."""

    def load_my_benchmark(self):
        """Load my 250-row benchmark."""
        with open('golden/chicago_spending_benchmark.json') as f:
            return json.load(f)

    def load_cowork_benchmark(self):
        """Load Cowork 236-row benchmark."""
        data = []
        with open('golden/geocode_benchmark_wardwise_v1.csv') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data

    def run_cascade_integrated(self, location_text, ward=None):
        """Run full cascade: grammar → normalize → parse → match stages."""
        # Step 1: Classify grammar
        grammar = GrammarClassifier.classify(location_text, ward)

        # Step 2: Normalize
        normalized = normalize(location_text)

        # Step 3: Parse components
        parsed = AddressParser.parse(normalized)

        # Step 4: Run matching cascade (stages 1-5) against mock DB
        mock_db = MockHolosDB()
        cascade = GeocodeCascade(mock_db)

        # Simplified cascade for testing: try address point exact match first
        if parsed.number and parsed.street:
            # Stage 1: Address point exact
            result = cascade.stage_1_address_point(normalized, parsed, location_text)
            if result and result.score > 0:
                return {
                    'grammar': grammar.grammar,
                    'stage': result.stage,
                    'method': result.method,
                    'score': result.score,
                    'coordinates': result.coordinates,
                }

        # Fallback: stage 8 (review queue)
        return {
            'grammar': grammar.grammar,
            'stage': 8,
            'method': 'needs_review',
            'score': 0.0,
            'coordinates': None,
        }

    def test_cascade_on_my_benchmark(self):
        """Run cascade on my 250-row benchmark and measure accuracy."""
        benchmark = self.load_my_benchmark()

        results = defaultdict(lambda: {'correct': 0, 'total': 0, 'examples': []})

        for row in benchmark:
            location = row['location_text']
            expected_grammar = row['expected_grammar']
            expected_coords = row['expected_coords']

            # Run cascade
            result = self.run_cascade_integrated(location, ward=row['ward'])

            results[expected_grammar]['total'] += 1

            # Score: grammar correct + coordinates within 100m
            grammar_correct = result['grammar'] == expected_grammar
            coords_correct = False
            if result['coordinates'] and expected_coords:
                dist = math.sqrt(
                    (result['coordinates'][0] - expected_coords[0])**2 +
                    (result['coordinates'][1] - expected_coords[1])**2
                )
                coords_correct = dist < 0.01  # ~1km tolerance for mock data

            if grammar_correct and coords_correct:
                results[expected_grammar]['correct'] += 1
            elif len(results[expected_grammar]['examples']) < 2:
                results[expected_grammar]['examples'].append({
                    'location': location[:50],
                    'expected_grammar': expected_grammar,
                    'got_grammar': result['grammar'],
                    'stage': result['stage'],
                })

        print("\n=== Cascade Accuracy on My Benchmark (250 rows) ===")
        total_correct = 0
        total_rows = 0
        for grammar in sorted(results.keys()):
            stats = results[grammar]
            correct = stats['correct']
            total = stats['total']
            pct = 100 * correct / total if total > 0 else 0
            total_correct += correct
            total_rows += total
            print(f"  {grammar:25s}: {correct}/{total} ({pct:5.1f}%)")

            if stats['examples']:
                for ex in stats['examples'][:1]:
                    print(f"    ✗ {ex['location']} (grammar: {ex['expected_grammar']} vs {ex['got_grammar']}, stage: {ex['stage']})")

        print(f"\nOverall: {total_correct}/{total_rows} ({100*total_correct/total_rows:.1f}%)")
        print("⚠️  Mock cascade: limited reference data, stage 1 only (no interpolation/intersection/segment)")

    def test_cascade_on_cowork_benchmark(self):
        """Run cascade on Cowork's 236-row independent benchmark."""
        benchmark = self.load_cowork_benchmark()

        results = defaultdict(lambda: {'correct': 0, 'total': 0})

        for row in benchmark:
            location = row['location_text']
            expected_grammar = row['expected_grammar']

            result = self.run_cascade_integrated(location, ward=row.get('ward'))

            results[expected_grammar]['total'] += 1

            # Score: grammar correct (mock only checks grammar, not coordinates)
            if result['grammar'] == expected_grammar:
                results[expected_grammar]['correct'] += 1

        print("\n=== Cascade Accuracy on Cowork Benchmark (236 rows) ===")
        total_correct = 0
        total_rows = 0
        for grammar in sorted(results.keys()):
            stats = results[grammar]
            correct = stats['correct']
            total = stats['total']
            pct = 100 * correct / total if total > 0 else 0
            total_correct += correct
            total_rows += total
            print(f"  {grammar:25s}: {correct}/{total} ({pct:5.1f}%)")

        print(f"\nOverall: {total_correct}/{total_rows} ({100*total_correct/total_rows:.1f}%)")
        print("⚠️  Mock cascade: limited reference data, stage 1 only")


if __name__ == '__main__':
    print("=" * 80)
    print("INTEGRATED CASCADE TESTS (Parse Pipeline + Mock Database)")
    print("=" * 80)

    tester = TestCascadeIntegrated()
    tester.test_cascade_on_my_benchmark()
    tester.test_cascade_on_cowork_benchmark()

    print("\n" + "=" * 80)
    print("Next: Populate hub with reference data, implement stages 0/6/7, iterate to ≥90%")
    print("=" * 80)
