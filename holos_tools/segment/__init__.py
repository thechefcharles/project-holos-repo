"""Segment: break infrastructure into block-level units with distance metadata.

Phase 1 Step 6: Infrastructure segmentation workflow
- Load alley and street centerlines
- Find street/alley intersections (block boundaries)
- Segment alleys at intersections
- Calculate segment length and distance from block start
- Store with metadata for analysis and spending allocation
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import typer
import math

app = typer.Typer(help="Segment: break infrastructure into block-level units")


def distance_between_points(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lon points in meters (Haversine formula)."""
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def line_length(coords: List[Tuple[float, float]]) -> float:
    """Calculate total length of a line in meters.

    Args:
        coords: [(lon, lat), ...]

    Returns:
        Total length in meters
    """
    total = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        total += distance_between_points(lat1, lon1, lat2, lon2)
    return total


def segment_line_by_points(line_coords: List[Tuple[float, float]],
                          segment_points: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
    """Break a line into segments at specified points.

    Args:
        line_coords: [(lon, lat), ...] - the line to segment
        segment_points: [(lon, lat), ...] - points where to break the line

    Returns:
        List of segments, each with start/end coords and distance from start
    """
    # Find indices in line_coords closest to each segment point
    segment_indices = []
    for seg_point in segment_points:
        closest_idx = 0
        min_dist = float('inf')

        for i, line_point in enumerate(line_coords):
            dist = distance_between_points(seg_point[1], seg_point[0], line_point[1], line_point[0])
            if dist < min_dist:
                min_dist = dist
                closest_idx = i

        segment_indices.append(closest_idx)

    # Sort indices
    segment_indices.sort()
    segment_indices = list(set(segment_indices))  # Remove duplicates

    # Create segments between indices
    segments = []
    all_indices = [0] + segment_indices + [len(line_coords) - 1]
    all_indices = list(set(all_indices))
    all_indices.sort()

    distance_from_start = 0.0

    for i in range(len(all_indices) - 1):
        start_idx = all_indices[i]
        end_idx = all_indices[i + 1]

        segment_coords = line_coords[start_idx:end_idx+1]
        segment_len = line_length(segment_coords)

        segments.append({
            'start_index': start_idx,
            'end_index': end_idx,
            'coordinates': segment_coords,
            'length_m': segment_len,
            'length_ft': segment_len * 3.28084,
            'distance_from_start_m': distance_from_start,
            'distance_from_start_ft': distance_from_start * 3.28084,
        })

        distance_from_start += segment_len

    return segments


@app.command()
def alleys_by_block(
    output_path: str = typer.Option(
        None,
        help="Output path for segmented alleys (auto-generate if not provided)"
    ),
):
    """Segment alleys into block-level units with distance metadata.

    This workflow:
    1. Creates synthetic alley segments for pilot
    2. Assigns each segment to a street block
    3. Calculates segment length and distance from block start
    4. Outputs with metadata for spending allocation

    Production workflow will:
    1. Load real alley centerlines from PostGIS
    2. Load street centerlines to find intersections
    3. Segment alleys at street intersections
    4. Allocate spending to segments based on project locations

    Example:
      holos segment alleys-by-block
    """

    typer.echo("📍 Segmenting alleys by block...\n")

    # Pilot: Create synthetic alley segments
    # In production: these would be loaded from PostGIS + real street intersections
    alley_segments = [
        {
            "alley_id": "alley_001",
            "name": "Alley between California & Francisco",
            "block": "2700-2800 W Shakespeare Ave",
            "centerline": [
                [-87.6972, 41.9206],
                [-87.6972, 41.9201]
            ],
            "intersecting_streets": [
                {"name": "W Shakespeare Ave", "coord": [-87.6972, 41.9206]},
                {"name": "W Palmer St", "coord": [-87.6972, 41.9201]}
            ]
        },
        {
            "alley_id": "alley_002",
            "name": "Alley at Chicago & Bishop",
            "block": "1500-1600 W Chicago Ave",
            "centerline": [
                [-87.6641, 41.8966],
                [-87.6636, 41.8966]
            ],
            "intersecting_streets": [
                {"name": "N Bishop St", "coord": [-87.6641, 41.8966]},
                {"name": "N Armour St", "coord": [-87.6636, 41.8966]}
            ]
        },
        {
            "alley_id": "alley_003",
            "name": "Alley at Bloomingdale",
            "block": "2800-2900 W Bloomingdale Ave",
            "centerline": [
                [-87.698, 41.9140],
                [-87.6975, 41.9140]
            ],
            "intersecting_streets": [
                {"name": "N Claremont Ave", "coord": [-87.698, 41.9140]},
                {"name": "N Ashland Ave", "coord": [-87.6975, 41.9140]}
            ]
        }
    ]

    segments_output = []

    for alley in alley_segments:
        alley_id = alley["alley_id"]

        # Segment the alley at street intersections
        intersection_points = [s["coord"] for s in alley["intersecting_streets"]]
        segments = segment_line_by_points(alley["centerline"], intersection_points)

        typer.echo(f"✓ {alley_id}: {len(segments)} segments")

        for seg_idx, segment in enumerate(segments):
            segment_id = f"{alley_id}_seg{seg_idx+1}"

            segment_output = {
                "segment_id": segment_id,
                "alley_id": alley_id,
                "alley_name": alley["name"],
                "block": alley["block"],
                "segment_number": seg_idx + 1,
                "total_segments": len(segments),
                "coordinates": segment["coordinates"],
                "length_m": round(segment["length_m"], 2),
                "length_ft": round(segment["length_ft"], 2),
                "distance_from_start_m": round(segment["distance_from_start_m"], 2),
                "distance_from_start_ft": round(segment["distance_from_start_ft"], 2),
                "intersecting_streets": alley["intersecting_streets"],
            }

            segments_output.append(segment_output)

            typer.echo(f"  Segment {seg_idx+1}: {segment['length_ft']:.1f} ft long")

    # Output results
    if output_path is None:
        output_path = "data/ward01_alleys_segmented.json"

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "metadata": {
            "ward": 1,
            "year": 2017,
            "segmentation_type": "alley_by_block",
            "method": "street_intersection_division",
            "unit": "feet",
            "note": "Pilot segmentation using synthetic data; production will use real street intersections from PostGIS"
        },
        "segments": segments_output
    }

    with open(out_file, 'w') as f:
        json.dump(result, f, indent=2)

    typer.echo(f"\n✓ Segmentation complete")
    typer.echo(f"  Total segments: {len(segments_output)}")
    typer.echo(f"  Output: {out_file}")

    # Summary statistics
    total_length_ft = sum(s["length_ft"] for s in segments_output)
    typer.echo(f"\n📊 Summary:")
    typer.echo(f"  Total alley length: {total_length_ft:.1f} ft")
    typer.echo(f"  Average segment length: {total_length_ft/len(segments_output):.1f} ft")
    typer.echo(f"  Alleys: {len(alley_segments)}")
    typer.echo(f"  Segments: {len(segments_output)}")


if __name__ == "__main__":
    app()
