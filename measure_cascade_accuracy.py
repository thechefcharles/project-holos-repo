#!/usr/bin/env python3
"""
Measure geocode cascade accuracy on both benchmarks (250-row + 236-row).
Reports per-grammar accuracy: correct / escalated / wrong.
"""

import json
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

# Add repo to path
sys.path.insert(0, str(Path(__file__).parent))

from holos_tools.geocode.cascade import GeocodeCascade, PostgresDB


@dataclass
class AccuracyRow:
    """A single row's accuracy measurement."""
    address: str
    grammar: str
    expected_lat: float
    expected_lon: float
    result_lat: float = None
    result_lon: float = None
    distance_m: float = None
    correct: bool = False
    escalated: bool = False
    wrong: bool = False


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two points."""
    from math import radians, cos, sin, asin, sqrt
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r


def measure_benchmark(cascade: GeocodeCascade, benchmark_file: str, benchmark_name: str) -> Dict:
    """Measure cascade accuracy on a benchmark."""
    print(f"\n{'='*80}")
    print(f"MEASURING: {benchmark_name}")
    print(f"{'='*80}")

    results: List[AccuracyRow] = []

    # Load benchmark
    if benchmark_file.endswith('.json'):
        with open(benchmark_file) as f:
            rows = json.load(f)
    else:  # CSV
        with open(benchmark_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    print(f"Loaded {len(rows)} benchmark rows")

    # Measure each row
    for i, row in enumerate(rows):
        address = row.get('address') or row.get('location_text') or row.get('location_text_norm') or row.get('location')
        grammar = row.get('expected_grammar') or row.get('grammar') or row.get('location_grammar') or 'unknown'

        # Handle expected_coords as [lon, lat] array
        coords = row.get('expected_coords')
        if coords and isinstance(coords, list):
            expected_lon, expected_lat = coords[0], coords[1]
        else:
            expected_lat = float(row.get('lat') or row.get('expected_lat') or 0)
            expected_lon = float(row.get('lon') or row.get('expected_lon') or 0)

        # Run cascade
        try:
            result = cascade.geocode(address, ward=row.get('ward'))
        except Exception as e:
            print(f"  [{i+1:3d}] ERROR: {address[:50]:50s} {grammar:20s} | {str(e)[:60]}")
            acc = AccuracyRow(
                address=address, grammar=grammar,
                expected_lat=expected_lat, expected_lon=expected_lon,
                wrong=True
            )
            results.append(acc)
            continue

        # Score the result
        if result.coordinates is None:
            # Escalated (no match)
            acc = AccuracyRow(
                address=address, grammar=grammar,
                expected_lat=expected_lat, expected_lon=expected_lon,
                escalated=True
            )
        else:
            result_lon, result_lat = result.coordinates
            distance = haversine_distance(
                expected_lat, expected_lon,
                result_lat, result_lon
            )

            if distance <= 100:  # Within 100m tolerance
                acc = AccuracyRow(
                    address=address, grammar=grammar,
                    expected_lat=expected_lat, expected_lon=expected_lon,
                    result_lat=result_lat, result_lon=result_lon,
                    distance_m=distance,
                    correct=True
                )
            else:
                # Confidently wrong (returned something, but >100m off)
                acc = AccuracyRow(
                    address=address, grammar=grammar,
                    expected_lat=expected_lat, expected_lon=expected_lon,
                    result_lat=result_lat, result_lon=result_lon,
                    distance_m=distance,
                    wrong=True
                )

        results.append(acc)

        # Print progress every 25 rows
        if (i + 1) % 25 == 0:
            correct_so_far = sum(1 for r in results if r.correct)
            escalated_so_far = sum(1 for r in results if r.escalated)
            wrong_so_far = sum(1 for r in results if r.wrong)
            pct = (correct_so_far + escalated_so_far) / len(results) * 100
            print(f"  [{i+1:3d}/{len(rows)}] {correct_so_far:3d} correct, {escalated_so_far:3d} escalated, {wrong_so_far:3d} wrong ({pct:.1f}%)")

    # Report per-grammar
    print(f"\n{'-'*80}")
    print("PER-GRAMMAR ACCURACY")
    print(f"{'-'*80}")

    grammars = set(r.grammar for r in results)
    grammar_stats = {}

    for grammar in sorted(grammars):
        grammar_rows = [r for r in results if r.grammar == grammar]
        correct = sum(1 for r in grammar_rows if r.correct)
        escalated = sum(1 for r in grammar_rows if r.escalated)
        wrong = sum(1 for r in grammar_rows if r.wrong)
        total = len(grammar_rows)
        accuracy = (correct + escalated) / total * 100 if total > 0 else 0

        grammar_stats[grammar] = {
            'correct': correct,
            'escalated': escalated,
            'wrong': wrong,
            'total': total,
            'accuracy': accuracy
        }

        print(f"{grammar:25s} {correct:3d} correct, {escalated:3d} escalated, {wrong:3d} wrong | {accuracy:6.1f}% ({total:3d} rows)")

    # Overall
    print(f"\n{'-'*80}")
    total_correct = sum(1 for r in results if r.correct)
    total_escalated = sum(1 for r in results if r.escalated)
    total_wrong = sum(1 for r in results if r.wrong)
    total_rows = len(results)
    overall_accuracy = (total_correct + total_escalated) / total_rows * 100

    print(f"OVERALL: {total_correct:3d} correct, {total_escalated:3d} escalated, {total_wrong:3d} wrong | {overall_accuracy:6.1f}% ({total_rows} rows)")

    return {
        'benchmark': benchmark_name,
        'total': total_rows,
        'correct': total_correct,
        'escalated': total_escalated,
        'wrong': total_wrong,
        'accuracy_pct': overall_accuracy,
        'grammar_stats': grammar_stats,
        'results': results
    }


def main():
    """Run measurement on both benchmarks."""

    # Connect to database
    print("Connecting to PostgreSQL...")
    try:
        db = PostgresDB()
        cascade = GeocodeCascade(db)
        print("✓ Connected")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)

    # Measure both benchmarks
    results_my = measure_benchmark(
        cascade,
        "golden/chicago_spending_benchmark.json",
        "My Benchmark (250 rows)"
    )

    results_cowork = measure_benchmark(
        cascade,
        "golden/geocode_benchmark_wardwise_v1.csv",
        "Cowork Benchmark (236 rows)"
    )

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"My Benchmark (250 rows):     {results_my['accuracy_pct']:6.1f}% ({results_my['correct']:3d}/{results_my['total']} correct+escalated)")
    print(f"Cowork Benchmark (236 rows): {results_cowork['accuracy_pct']:6.1f}% ({results_cowork['correct']+results_cowork['escalated']:3d}/{results_cowork['total']} correct+escalated)")

    avg_accuracy = (results_my['accuracy_pct'] + results_cowork['accuracy_pct']) / 2
    print(f"\nAverage Accuracy: {avg_accuracy:.1f}%")
    print(f"Target (Phase 1): 90.0%")
    print(f"Gap: {90.0 - avg_accuracy:.1f}%")

    db.close()


if __name__ == "__main__":
    main()
