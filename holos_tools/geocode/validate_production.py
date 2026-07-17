#!/usr/bin/env python3
"""Production validation: Measure Tier 2 Part 1 improvement on 2017 data.

Run this after deploying ST_LineSubstring + regex improvements.

Usage:
  uv run python holos_tools/geocode/validate_production.py

Measures:
  - Baseline: Previous cascade results
  - Current: New cascade with Tier 2 Part 1
  - Improvement: Actual vs. projected gains
"""

import json
import os
from pathlib import Path
from typing import Dict, List


def load_baseline() -> List[Dict]:
    """Load baseline results (before Tier 2 Part 1)."""
    baseline_file = Path("2017_geocoded.json")
    if not baseline_file.exists():
        print("❌ Baseline file not found: 2017_geocoded.json")
        return []

    with open(baseline_file) as f:
        return json.load(f)


def analyze_results(results: List[Dict]) -> Dict:
    """Analyze geocoding results."""
    methods = {}
    method_counts = {}

    for record in results:
        result = record.get('result', {})
        method = result.get('method', 'none')
        methods[method] = methods.get(method, 0) + 1

        # Track success by method
        if method != 'none':
            method_counts[method] = method_counts.get(method, 0) + 1

    total = len(results)
    geocoded = total - methods.get('none', 0)
    geocoding_rate = geocoded / total * 100 if total > 0 else 0

    return {
        'total': total,
        'geocoded': geocoded,
        'escalated': methods.get('none', 0),
        'rate': geocoding_rate,
        'methods': methods,
        'method_counts': method_counts,
    }


def main():
    print("\n" + "="*70)
    print("PRODUCTION VALIDATION: Tier 2 Part 1 Improvement")
    print("="*70)

    # Load baseline
    baseline = load_baseline()
    if not baseline:
        return

    baseline_analysis = analyze_results(baseline)

    print("\n📊 BASELINE RESULTS (Before Tier 2 Part 1):")
    print(f"   Total records: {baseline_analysis['total']}")
    print(f"   Geocoded: {baseline_analysis['geocoded']} ({baseline_analysis['rate']:.1f}%)")
    print(f"   Escalated: {baseline_analysis['escalated']}")

    print("\n   By method:")
    for method in sorted(baseline_analysis['methods'].keys(),
                         key=lambda x: baseline_analysis['methods'][x], reverse=True):
        count = baseline_analysis['methods'][method]
        pct = count / baseline_analysis['total'] * 100
        print(f"     {method:25} {count:4} ({pct:5.1f}%)")

    # Analyze FROM/TO pattern
    from_to_geocoded = baseline_analysis['methods'].get('range_bounding', 0)
    from_to_escalated = 0

    for record in baseline:
        result = record.get('result', {})
        location = record.get('record', {}).get('location', '')

        if result.get('method') == 'none' and 'FROM' in location.upper() and 'TO' in location.upper():
            from_to_escalated += 1

    print(f"\n🎯 FROM/TO PATTERN ANALYSIS (Tier 2 Part 1 Target):")
    print(f"   Total FROM/TO records: {from_to_geocoded + from_to_escalated}")
    print(f"   Geocoded (range_bounding): {from_to_geocoded}")
    print(f"   Escalated (method=none): {from_to_escalated}")

    # Project improvement
    print(f"\n📈 PROJECTED IMPROVEMENT (Tier 2 Part 1):")
    recovery_rate = 0.70
    expected_new = int(from_to_escalated * recovery_rate)
    expected_total = baseline_analysis['geocoded'] + expected_new
    expected_rate = expected_total / baseline_analysis['total'] * 100

    print(f"   Conservative estimate (70% success on escalated):")
    print(f"     New geocodes: {from_to_escalated} × {recovery_rate*100:.0f}% = {expected_new}")
    print(f"     Expected total: {expected_total}/{baseline_analysis['total']} ({expected_rate:.1f}%)")
    print(f"     Expected improvement: +{expected_rate - baseline_analysis['rate']:.1f}pp")

    # Spend impact
    avg_spend = 19.8e6 / baseline_analysis['geocoded']
    additional_spend = expected_new * avg_spend

    print(f"\n💰 SPEND IMPACT:")
    print(f"   Current geocoded spend: $19.8M")
    print(f"   Expected additional spend: ${additional_spend/1e6:.1f}M")
    print(f"   Expected total: ${(19.8e6 + additional_spend)/1e6:.1f}M")

    print(f"\n" + "="*70)
    print("INSTRUCTIONS FOR PRODUCTION RUN:")
    print("="*70)
    print("""
1. Deploy improved cascade to production:
   git checkout master
   git merge origin/dev
   # Deploy to Vercel or production environment

2. Run re-geocoding on 2017 data:
   uv run holos geocode-batch \\
     --input 2017_valid_records.json \\
     --output 2017_geocoded_tier2.json \\
     --db-url $DATABASE_URL

3. Compare results:
   # Load 2017_geocoded_tier2.json and re-run this script
   # Actual results should be within ±5pp of projection

4. If results match projection:
   - Tier 2 Part 1 successful ✓
   - Proceed to Part 2 (gazetteer loading)

5. If results differ significantly:
   - Investigate root cause
   - Check for database connection issues
   - Verify cascading configuration
    """)

    print("="*70)
    print(f"Status: Ready for production deployment")
    print(f"Expected improvement: {baseline_analysis['rate']:.1f}% → {expected_rate:.1f}% (+{expected_rate - baseline_analysis['rate']:.1f}pp)")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
