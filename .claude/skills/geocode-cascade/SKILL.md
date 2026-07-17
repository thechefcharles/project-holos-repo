---
name: geocode-cascade
description: End-to-end geocoding on a location text or dataset—stages 0–8, measure accuracy
---

# /geocode-cascade — Geocoding pipeline

Runs the full geocoding cascade (8 stages) on a location or dataset, measuring accuracy against known results.

## Stages

1. **Normalize** (0a) — lowercase, diacritics, whitespace
2. **Parse** (0b–0c) — number, predir, street, suffix, postdir
3. **Single address** (1) — exact address-point match
4. **Address range** (2) — street segment with FROM/TO interpolation
5. **Intersection** (3) — cross-street geometry
6. **Street segment** (4) — bounded street range
7. **Gazetteer** (5) — named place (park, library, fire station)
8. **External geocoder** (6) — Census/Google fallback
9. **LLM select** (7) — human-in-the-loop if ambiguous

## Usage

```bash
# Single location
/geocode-cascade "123 N CLARK ST"

# Dataset (CSV)
/geocode-cascade --input staging.spend_records --output staging.spend_geocoded

# With ward constraint
/geocode-cascade "123 N CLARK ST" --ward 1
```

## When to use

- Testing a new location text pattern
- Measuring cascade accuracy (Tier 1 baseline, Tier 2 improvements)
- Debugging why an address escalated

## Output

```json
{
  "location_text": "123 N CLARK ST",
  "stage": 2,
  "method": "address_point_exact",
  "coordinates": [-87.6314, 41.8879],
  "score": 1.0,
  "geometry_type": "POINT"
}
```

**Score interpretation:**
- 1.0 = exact match
- 0.85 = interpolated (range or segment)
- 0.50 = lower-confidence match (escalate)
- null = no match (escalate to manual review)

---

**See also:** `/docs/tech-spec.md` Chain A1 (geocoding cascade), `holos_tools/geocode/cascade.py` (implementation)
