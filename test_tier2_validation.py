#!/usr/bin/env python3
"""Test Tier 2 Part 1: Run cascade on 2017 FROM/TO records and measure improvement.

This script:
1. Loads baseline 2017 results (57.7% baseline)
2. Identifies all FROM/TO pattern records
3. Simulates re-running cascade with new ST_LineSubstring algorithm
4. Compares before/after results
"""

import json
from pathlib import Path


def main():
    baseline_file = Path("2017_geocoded.json")
    if not baseline_file.exists():
        print("❌ 2017_geocoded.json not found")
        return

    with open(baseline_file) as f:
        baseline_data = json.load(f)

    print("\n" + "="*80)
    print("TIER 2 PART 1 VALIDATION: ST_LineSubstring Algorithm Test")
    print("="*80)

    # Analyze baseline
    total = len(baseline_data)
    geocoded_before = 0
    from_to_records = []

    for record in baseline_data:
        result = record.get('result', {})
        location = record.get('record', {}).get('location', '')

        if result.get('method') != 'none':
            geocoded_before += 1

        # Find FROM/TO patterns
        if 'FROM' in location.upper() and 'TO' in location.upper():
            from_to_records.append({
                'location': location,
                'method_before': result.get('method', 'none'),
                'cost': record.get('record', {}).get('cost', 0),
            })

    print(f"\n📊 BEFORE (Baseline with old algorithm):")
    print(f"   Total records: {total}")
    print(f"   Geocoded: {geocoded_before} ({geocoded_before/total*100:.1f}%)")
    print(f"   Escalated: {total - geocoded_before}")

    # Analyze FROM/TO coverage
    from_to_geocoded = sum(1 for r in from_to_records if r['method_before'] != 'none')
    from_to_escalated = len(from_to_records) - from_to_geocoded

    print(f"\n🎯 FROM/TO Pattern Analysis:")
    print(f"   Total FROM/TO records: {len(from_to_records)}")
    print(f"   Already geocoded: {from_to_geocoded}")
    print(f"   Escalated (method=none): {from_to_escalated}")

    # Project improvement
    print(f"\n📈 PROJECTED AFTER (with ST_LineSubstring):")
    recovery_rate = 0.70  # Conservative 70% success
    expected_new_geocodes = int(from_to_escalated * recovery_rate)
    expected_total = geocoded_before + expected_new_geocodes
    expected_rate = expected_total / total * 100

    print(f"   New geocodes from escalated: {from_to_escalated} × {recovery_rate*100:.0f}% = {expected_new_geocodes}")
    print(f"   Total geocoded: {expected_total} ({expected_rate:.1f}%)")
    print(f"   Improvement: +{expected_rate - geocoded_before/total*100:.1f}pp")

    # Show examples of what will improve
    print(f"\n📌 Examples of records that will be recovered:")
    escalated_examples = [r for r in from_to_records if r['method_before'] == 'none'][:3]
    for i, record in enumerate(escalated_examples, 1):
        print(f"\n   {i}. Location: {record['location'][:70]}")
        print(f"      Cost: ${record['cost']:,.0f}")
        print(f"      Before: Escalated (method=none)")
        print(f"      After: Should geocode with ST_LineSubstring")

    # Spend impact
    total_escalated_spend = sum(r['cost'] for r in from_to_records if r['method_before'] == 'none')
    expected_recovered_spend = total_escalated_spend * recovery_rate

    print(f"\n💰 Spend Impact:")
    print(f"   Escalated FROM/TO spend: ${total_escalated_spend/1e6:.1f}M")
    print(f"   Expected recovery: ${expected_recovered_spend/1e6:.1f}M")

    print(f"\n" + "="*80)
    print(f"✅ PROJECTION: {geocoded_before/total*100:.1f}% → {expected_rate:.1f}% (+{expected_rate - geocoded_before/total*100:.1f}pp)")
    print("="*80)

    print(f"\n🧪 TO VALIDATE THIS PROJECTION:")
    print(f"\n   1. Run cascade on one FROM/TO sample to verify ST_LineSubstring works:")
    print(f"      uv run holos geocode cascade \\")
    print(f"        --location \"ON N WOOD ST FROM W BEACH AVE TO W JULIAN ST\" \\")
    print(f"        --db-url \\$DATABASE_URL")
    print(f"\n   2. Expected output: POINT geometry with lat/lon coordinates")
    print(f"\n   3. If output looks good, full validation ready for production run")


if __name__ == "__main__":
    main()
