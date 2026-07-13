"""Tier-1 validators: self-consistency checks (no external answer key needed)."""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ValidationResult:
    """Single validation result."""
    check_name: str
    passed: bool
    message: str
    details: dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


# Chicago bounding box (approximate)
CHICAGO_BBOX = {
    "min_lon": -87.95,
    "max_lon": -87.52,
    "min_lat": 41.64,
    "max_lat": 42.02,
}

# Expected program size per ward/year
EXPECTED_PROGRAM_SIZE_PER_WARD = 1_300_000  # ~$1.3M per ward
EXPECTED_ANNUAL_TOTAL = 66_000_000  # ~$66M per year (50 wards × $1.3M)
BUDGET_TOLERANCE = 0.15  # 15% tolerance for program size


def validate_field_completeness(record: dict) -> ValidationResult:
    """Check: ward, year, cost, location are all present."""
    required_fields = ["ward", "year", "cost", "location"]
    missing = [f for f in required_fields if f not in record or record[f] is None or record[f] == ""]

    if missing:
        return ValidationResult(
            check_name="field_completeness",
            passed=False,
            message=f"Missing required fields: {', '.join(missing)}",
            details={"missing_fields": missing},
        )

    return ValidationResult(
        check_name="field_completeness",
        passed=True,
        message="All required fields present",
    )


def validate_bbox_check(lon: float, lat: float) -> ValidationResult:
    """Check: coordinate within Chicago bounding box (catches lon/lat swap)."""
    if lon < CHICAGO_BBOX["min_lon"] or lon > CHICAGO_BBOX["max_lon"]:
        return ValidationResult(
            check_name="bbox_check",
            passed=False,
            message=f"Longitude {lon} outside Chicago range [{CHICAGO_BBOX['min_lon']}, {CHICAGO_BBOX['max_lon']}]",
            details={"lon": lon, "lat": lat, "reason": "out_of_range_lon"},
        )

    if lat < CHICAGO_BBOX["min_lat"] or lat > CHICAGO_BBOX["max_lat"]:
        return ValidationResult(
            check_name="bbox_check",
            passed=False,
            message=f"Latitude {lat} outside Chicago range [{CHICAGO_BBOX['min_lat']}, {CHICAGO_BBOX['max_lat']}]",
            details={"lon": lon, "lat": lat, "reason": "out_of_range_lat"},
        )

    return ValidationResult(
        check_name="bbox_check",
        passed=True,
        message=f"Coordinate ({lon}, {lat}) within Chicago bbox",
    )


def validate_ward_containment(
    db_url: str, lon: float, lat: float, ward: int, year: int = 2023
) -> ValidationResult:
    """Check: geocoded point falls inside assigned ward (PostGIS point-in-polygon)."""
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor(cursor_factory=DictCursor)

        # Query: does the point fall inside the ward?
        query = """
        SELECT EXISTS(
            SELECT 1 FROM ref.wards w
            WHERE w.ward_number = %s
            AND w.vintage = %s
            AND ST_Contains(w.geom, ST_Point(%s, %s))
        ) as contained
        """

        cur.execute(query, (ward, year, lon, lat))
        result = cur.fetchone()
        contained = result["contained"]

        cur.close()
        conn.close()

        if not contained:
            return ValidationResult(
                check_name="ward_containment",
                passed=False,
                message=f"Point ({lon}, {lat}) does NOT fall inside Ward {ward}",
                details={"lon": lon, "lat": lat, "ward": ward},
            )

        return ValidationResult(
            check_name="ward_containment",
            passed=True,
            message=f"Point ({lon}, {lat}) contained in Ward {ward}",
        )

    except Exception as e:
        return ValidationResult(
            check_name="ward_containment",
            passed=False,
            message=f"Ward containment check failed (DB error): {e}",
            details={"error": str(e)},
        )


def validate_budget_tieout(
    records: List[dict], expected_total: float = EXPECTED_ANNUAL_TOTAL
) -> ValidationResult:
    """Check: total spend per year/ward matches known program size."""
    if not records:
        return ValidationResult(
            check_name="budget_tieout",
            passed=False,
            message="No records to validate",
        )

    # Group by ward and year
    by_ward_year = {}
    total_cost = 0

    for rec in records:
        ward = rec.get("ward")
        year = rec.get("year")
        cost = rec.get("cost", 0)

        if ward is None or year is None:
            continue

        key = (ward, year)
        if key not in by_ward_year:
            by_ward_year[key] = 0
        by_ward_year[key] += cost
        total_cost += cost

    # Check: total is within tolerance of expected
    if expected_total == 0:
        return ValidationResult(
            check_name="budget_tieout",
            passed=False,
            message="Expected total is zero",
        )

    variance = abs(total_cost - expected_total) / expected_total

    if variance > BUDGET_TOLERANCE:
        return ValidationResult(
            check_name="budget_tieout",
            passed=False,
            message=f"Total spend ${total_cost:,} is {variance*100:.1f}% off expected ${expected_total:,}",
            details={
                "actual_total": total_cost,
                "expected_total": expected_total,
                "variance_pct": variance * 100,
                "tolerance_pct": BUDGET_TOLERANCE * 100,
            },
        )

    return ValidationResult(
        check_name="budget_tieout",
        passed=True,
        message=f"Total spend ${total_cost:,} within {BUDGET_TOLERANCE*100:.0f}% of expected ${expected_total:,}",
        details={"actual_total": total_cost, "expected_total": expected_total},
    )
