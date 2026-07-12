"""Cascade accuracy tests using real PostgreSQL database and reference data.

Measures GEOCODING accuracy (not grammar classification) on dual benchmarks.
"""

import json
import csv
import math
from pathlib import Path
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from holos_tools.geocode.grammar import GrammarClassifier
from holos_tools.geocode.normalize import normalize
from holos_tools.geocode.parser import AddressParser
from holos_tools.geocode.cascade import GeocodeCascade, PostgresDB


def distance_meters(lon1, lat1, lon2, lat2):
    """Simple great-circle distance (degrees to approximate meters, good enough for Chicago)."""
    # ~111 km per degree at equator
    lon_diff = (lon2 - lon1) * 111000 * math.cos(math.radians((lat1 + lat2) / 2))
    lat_diff = (lat2 - lat1) * 111000
    return math.sqrt(lon_diff**2 + lat_diff**2)


class TestCascadeRealDB:
    """Cascade tests with real PostgreSQL and reference data."""

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

    def run_cascade_real_db(self, location_text, ward=None):
        """Run full cascade against real PostgreSQL database."""
        try:
            # Step 1: Classify grammar
            grammar = GrammarClassifier.classify(location_text, ward)

            # Step 2: Normalize
            normalized = normalize(location_text)

            # Step 3: Parse components
            parsed = AddressParser.parse(normalized)

            # Step 4: Run matching cascade (stages 1-5) against real DB
            db = PostgresDB()
            cascade = GeocodeCascade(db)

            result = cascade.geocode(location_text, ward)
            db.close()

            return {
                'grammar': grammar.grammar,
                'stage': result.stage,
                'method': result.method,
                'score': result.score,
                'coordinates': result.coordinates,
                'geometry_type': result.geometry_type,
            }
        except Exception as e:
            print(f"Error processing '{location_text}': {e}")
            return {
                'grammar': 'error',
                'stage': 8,
                'method': 'error',
                'score': 0.0,
                'coordinates': None,
                'geometry_type': 'POINT',
            }

    def test_cascade_on_my_benchmark(self):
        """Run cascade on my 250-row benchmark and measure GEOCODING accuracy."""
        benchmark = self.load_my_benchmark()

        results = defaultdict(lambda: {'correct': 0, 'total': 0, 'examples': []})

        for i, row in enumerate(benchmark):
            location = row['location_text']
            expected_grammar = row['expected_grammar']
            expected_coords = row['expected_coords']

            # Run cascade
            result = self.run_cascade_real_db(location, ward=row.get('ward'))

            results[expected_grammar]['total'] += 1

            # Score: grammar correct + coordinates within 100m (0.001 degrees ≈ 111m)
            grammar_correct = result['grammar'] == expected_grammar
            coords_correct = False
            if result['coordinates'] and expected_coords:
                dist = distance_meters(
                    result['coordinates'][0], result['coordinates'][1],
                    expected_coords[0], expected_coords[1]
                )
                coords_correct = dist < 100  # 100m tolerance

            if grammar_correct and coords_correct:
                results[expected_grammar]['correct'] += 1
            elif len(results[expected_grammar]['examples']) < 2:
                results[expected_grammar]['examples'].append({
                    'location': location[:50],
                    'expected_grammar': expected_grammar,
                    'got_grammar': result['grammar'],
                    'stage': result['stage'],
                    'coords': result['coordinates'],
                })

            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(benchmark)} rows...")

        print("\n=== GEOCODING Accuracy on My Benchmark (250 rows) ===")
        total_correct = 0
        total_rows = 0
        for grammar in sorted(results.keys()):
            stats = results[grammar]
            correct = stats['correct']
            total = stats['total']
            pct = 100 * correct / total if total > 0 else 0
            total_correct += correct
            total_rows += total
            print(f"  {grammar:25s}: {correct:3d}/{total:3d} ({pct:5.1f}%)")

            if stats['examples']:
                for ex in stats['examples'][:1]:
                    print(f"    ✗ {ex['location']} (stage {ex['stage']})")

        overall_pct = 100 * total_correct / total_rows if total_rows > 0 else 0
        print(f"\nOverall GEOCODING: {total_correct}/{total_rows} ({overall_pct:.1f}%)")

    def test_cascade_on_cowork_benchmark(self):
        """Run cascade on Cowork's 236-row independent benchmark."""
        benchmark = self.load_cowork_benchmark()

        results = defaultdict(lambda: {'correct': 0, 'total': 0})

        for i, row in enumerate(benchmark):
            location = row['location_text']
            expected_grammar = row['expected_grammar']

            result = self.run_cascade_real_db(location, ward=row.get('ward'))

            results[expected_grammar]['total'] += 1

            # Score: grammar correct (coordinates not in Cowork benchmark)
            if result['grammar'] == expected_grammar:
                results[expected_grammar]['correct'] += 1

            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(benchmark)} rows...")

        print("\n=== GRAMMAR Classification on Cowork Benchmark (236 rows) ===")
        total_correct = 0
        total_rows = 0
        for grammar in sorted(results.keys()):
            stats = results[grammar]
            correct = stats['correct']
            total = stats['total']
            pct = 100 * correct / total if total > 0 else 0
            total_correct += correct
            total_rows += total
            print(f"  {grammar:25s}: {correct:3d}/{total:3d} ({pct:5.1f}%)")

        overall_pct = 100 * total_correct / total_rows if total_rows > 0 else 0
        print(f"\nOverall GRAMMAR: {total_correct}/{total_rows} ({overall_pct:.1f}%)")
        print("(Note: Cowork benchmark has grammar labels but no coordinate ground truth)")


if __name__ == '__main__':
    print("=" * 80)
    print("CASCADE TESTS WITH REAL DATABASE (PostgreSQL + Reference Data)")
    print("=" * 80)

    tester = TestCascadeRealDB()

    print("\n*** Testing on My Benchmark (250 rows) ***")
    tester.test_cascade_on_my_benchmark()

    print("\n*** Testing on Cowork Benchmark (236 rows) ***")
    tester.test_cascade_on_cowork_benchmark()

    print("\n" + "=" * 80)
    print("If <90%: next step is Stage 6 (Census Geocoder + Nominatim)")
    print("=" * 80)
