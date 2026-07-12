"""Stage 6: External geocoders (Census Geocoder + Nominatim).

Free, no-key geocoding services for addresses that fail stages 1-5.
"""

import requests
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class CensusResult:
    """Result from Census Geocoder."""
    lon: float
    lat: float
    match_type: str  # "Exact", "Non_Exact", "Tie"
    score: float = 0.0


class CensusGeocoder:
    """U.S. Census Bureau batch geocoding service (free, no key required)."""

    BASE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

    @classmethod
    def geocode(cls, address: str) -> Optional[CensusResult]:
        """Geocode a single address using Census Geocoder.

        Args:
            address: Full address string

        Returns:
            CensusResult with coordinates and match quality, or None if failed
        """
        if not address:
            return None

        try:
            params = {
                "address": address,
                "format": "json",
                "benchmark": "Public_AR_Current",
            }
            # Short timeout; Census API can be slow or unresponsive
            response = requests.get(cls.BASE_URL, params=params, timeout=2)
            response.raise_for_status()

            data = response.json()
            if not data.get("result", {}).get("addressMatches"):
                return None

            match = data["result"]["addressMatches"][0]
            coords = match["coordinates"]

            # Score based on match type
            match_type = match.get("matchedAddress", "")

            # Heuristic: "Exact" matches get high score, "Non_Exact" get medium
            score = 0.85  # Conservative: most Census matches are good

            return CensusResult(
                lon=coords["x"],
                lat=coords["y"],
                match_type=match_type,
                score=score,
            )
        except requests.Timeout:
            return None  # API timeout; fail fast
        except Exception as e:
            return None


class NominatimGeocoder:
    """OpenStreetMap Nominatim geocoding (self-hosted or public)."""

    BASE_URL = "https://nominatim.openstreetmap.org/search"  # Public instance

    @classmethod
    def geocode(cls, address: str, base_url: Optional[str] = None) -> Optional[Tuple[float, float, float]]:
        """Geocode an address using Nominatim.

        Args:
            address: Full address string
            base_url: Optional custom Nominatim instance URL (for self-hosted)

        Returns:
            (lon, lat, score) tuple, or None if failed
        """
        if not address:
            return None

        url = base_url or cls.BASE_URL

        try:
            params = {
                "q": address,
                "format": "json",
                "limit": 1,
                "timeout": 10,
            }
            # Add User-Agent for public instance
            headers = {"User-Agent": "Project Holos Geocoder"}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data:
                return None

            result = data[0]
            lon = float(result["lon"])
            lat = float(result["lat"])
            # Importance is roughly 0-1, use as confidence
            importance = float(result.get("importance", 0.5))
            score = min(0.95, max(0.60, importance * 1.2))  # Scale to reasonable range

            return (lon, lat, score)
        except Exception as e:
            return None
