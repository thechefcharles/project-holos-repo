"""Phase 1 benchmark: Measure geocoding rate and accuracy improvements.

PHASE 1 ENHANCEMENT (2026-07-18): Quantify impact of:
- Address normalization (directional expansion, title case)
- Spatial validation layer (bounds, street overlap, ward match)

Benchmark dataset: 2017 aldermanic spending records (878 total, 43 failures from prior phase).
Expected improvements:
- Rate: 57.8% → 70%+ (target 80%+)
- Accuracy: 95% → 97%+ (target 98%+)

Run with: uv run pytest holos_tools/geocode/test_phase1_benchmark.py -xvs
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Tuple

import pytest

from holos_tools.geocode.cascade import GeocodeCascade, PostgresDB, GeocodeResult


@dataclass
class BenchmarkRecord:
    """Test record with expected answer and actual result."""
    record_id: str
    location_text: str
    ward: str
    expected_lon: float
    expected_lat: float
    result: GeocodeResult = None
    # Accuracy scoring (only if result exists)
    distance_meters: float = None
    is_correct: bool = False  # Within 100m of expected
    is_geocoded: bool = False  # Has a result


class Phase1Benchmark:
    """Benchmark framework for Phase 1 improvements."""

    ACCURACY_THRESHOLD_METERS = 100.0  # 100m = acceptable geocoding accuracy

    def __init__(self, db=None):
        """Initialize benchmark with optional database connection."""
        self.db = db or self._init_db()
        self.cascade = GeocodeCascade(self.db)
        self.records: List[BenchmarkRecord] = []

    def _init_db(self) -> PostgresDB:
        """Initialize database connection."""
        return PostgresDB()

    def load_test_set(self, csv_path: str) -> None:
        """Load 2017 spending records with known geocoded locations.

        CSV format: record_id,location_text,ward,expected_lon,expected_lat
        Expected data from core.spend_2017 with geocoding results.
        """
        if not os.path.exists(csv_path):
            pytest.skip(f"Test set not found: {csv_path}")

        self.records = []
        with open(csv_path, 'r') as f:
            # Skip header
            f.readline()
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 5:
                    record = BenchmarkRecord(
                        record_id=parts[0],
                        location_text=parts[1],
                        ward=parts[2],
                        expected_lon=float(parts[3]),
                        expected_lat=float(parts[4]),
                    )
                    self.records.append(record)

    def load_from_db(self, limit: int = 100) -> None:
        """Load test set directly from staging.spending_projects (2017 data).

        PHASE 1: Uses geocoding results as golden answers.
        """
        self.records = []
        sql = f"""
            SELECT
                row_id::text AS record_id,
                location_text_raw AS location_text,
                ward::text,
                ST_X(geom) AS expected_lon,
                ST_Y(geom) AS expected_lat
            FROM staging.spending_projects
            WHERE year = 2017
                AND geom IS NOT NULL
                AND ward IS NOT NULL
            LIMIT {limit}
        """
        results = self.db.execute(sql)
        for row in results:
            record = BenchmarkRecord(
                record_id=row['record_id'],
                location_text=row['location_text'],
                ward=row['ward'],
                expected_lon=float(row['expected_lon']),
                expected_lat=float(row['expected_lat']),
            )
            self.records.append(record)

    def run_benchmark(self) -> Tuple[float, float]:
        """Run Phase 1 benchmark on all records.

        Returns: (geocoding_rate_pct, accuracy_pct)
        """
        if not self.records:
            raise ValueError("No test records loaded")

        print(f"\nPhase 1 Benchmark: {len(self.records)} records")
        print("=" * 70)

        geocoded_count = 0
        correct_count = 0

        for i, record in enumerate(self.records):
            result = self.cascade.geocode(record.location_text, record.ward)
            record.result = result

            if result and result.coordinates:
                record.is_geocoded = True
                geocoded_count += 1

                # Measure distance to expected location
                distance = self._haversine(
                    result.coordinates[0], result.coordinates[1],
                    record.expected_lon, record.expected_lat
                )
                record.distance_meters = distance

                if distance <= self.ACCURACY_THRESHOLD_METERS:
                    record.is_correct = True
                    correct_count += 1

                status = "✓" if record.is_correct else "✗"
                print(f"[{i+1:3d}] {status} {record.record_id}: {record.location_text[:40]:<40} | "
                      f"distance={distance:.1f}m | stage={result.stage}")
            else:
                print(f"[{i+1:3d}] ✗ {record.record_id}: {record.location_text[:40]:<40} | "
                      f"NO RESULT (stage {result.stage if result else 'N/A'})")

        geocoding_rate = (geocoded_count / len(self.records)) * 100 if self.records else 0
        accuracy = (correct_count / geocoded_count) * 100 if geocoded_count > 0 else 0

        print("\n" + "=" * 70)
        print(f"RESULTS: {geocoded_count}/{len(self.records)} geocoded ({geocoding_rate:.1f}%)")
        print(f"ACCURACY: {correct_count}/{geocoded_count} correct ({accuracy:.1f}%)")
        print(f"COMPOSITE: {(geocoding_rate * accuracy / 100):.1f}%")
        print("=" * 70)

        return geocoding_rate, accuracy

    def report_failures(self) -> List[BenchmarkRecord]:
        """Report all records that failed geocoding or accuracy check."""
        failures = []
        for record in self.records:
            if not record.is_geocoded or (record.is_geocoded and not record.is_correct):
                failures.append(record)
        return failures

    @staticmethod
    def _haversine(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """Calculate distance between two points in meters (WGS84)."""
        import math

        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (math.sin(delta_phi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


# Test: Phase 1 geocoding rate and accuracy
@pytest.mark.integration
def test_phase1_rate_and_accuracy():
    """Benchmark Phase 1 improvements on 2017 dataset.

    Expected:
    - Rate: 57.8% → 70%+
    - Accuracy: 95% → 97%+
    """
    benchmark = Phase1Benchmark()

    # Load test set from database (or CSV if provided)
    try:
        benchmark.load_from_db(limit=100)
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

    rate, accuracy = benchmark.run_benchmark()

    # Phase 1 targets (not strict requirements, just track progress)
    print(f"\nPhase 1 Targets:")
    print(f"  Rate target: 70%+ (current: {rate:.1f}%)")
    print(f"  Accuracy target: 97%+ (current: {accuracy:.1f}%)")

    # Report failures for manual review
    failures = benchmark.report_failures()
    if failures:
        print(f"\n{len(failures)} failures (first 10):")
        for record in failures[:10]:
            reason = "NO RESULT" if not record.is_geocoded else f"{record.distance_meters:.1f}m away"
            print(f"  - {record.record_id}: {record.location_text[:50]} ({reason})")


if __name__ == "__main__":
    # Run benchmark standalone (not via pytest)
    benchmark = Phase1Benchmark()
    try:
        benchmark.load_from_db(limit=878)  # Full 2017 dataset
        rate, accuracy = benchmark.run_benchmark()

        # Export results as JSON
        results_path = "/tmp/phase1_benchmark.json"
        with open(results_path, 'w') as f:
            json.dump({
                'date': '2026-07-18',
                'phase': 'Phase 1 (normalization + spatial validation)',
                'geocoding_rate_pct': rate,
                'accuracy_pct': accuracy,
                'composite_accuracy_pct': (rate * accuracy / 100),
                'records_tested': len(benchmark.records),
            }, f, indent=2)
        print(f"\nResults saved to: {results_path}")
    except Exception as e:
        print(f"Error: {e}")
