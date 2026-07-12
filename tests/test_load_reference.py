"""Golden tests for holos load reference (Chain A2 reference data)."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from holos_tools.load import _load_config, _load_csv_to_postgis, reference


class TestLoadReference:
    """Golden tests for reference data loading."""

    @pytest.fixture
    def temp_project(self, tmp_path, monkeypatch):
        """Set up a temporary project with config and sample data."""
        monkeypatch.chdir(tmp_path)

        # Create config directory and sources.yaml
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        sources_yaml = """
chicago:
  reference_data:
    street_center_lines:
      id: "6imu-meau"
      tier: "public"
      rights: "public-record"
      role: "geocoding backbone"
    ward_boundaries_2023:
      id: "p293-wvbd"
      tier: "public"
      rights: "public-record"
      role: "containment validation"
    service_requests_311:
      id: "v6vf-nfxy"
      tier: "public"
      rights: "public-record"
      role: "complaint coverage"
"""
        (config_dir / "sources.yaml").write_text(sources_yaml)

        # Create sample harvest directory structure
        raw_dir = tmp_path / "raw" / "socrata"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Create sample centerlines CSV with geometry (WKT)
        centerlines_csv = raw_dir / "6imu-meau" / "2026-07-12" / "6imu-meau.csv"
        centerlines_csv.parent.mkdir(parents=True, exist_ok=True)
        centerlines_df = pd.DataFrame({
            "id": [1, 2, 3],
            "street_name": ["Michigan Ave", "State St", "Madison Ave"],
            "shape": [
                "LINESTRING(0 0, 1 0)",
                "LINESTRING(0 1, 1 1)",
                "LINESTRING(0 2, 1 2)"
            ],
        })
        centerlines_df.to_csv(centerlines_csv, index=False)

        # Create sample wards CSV with geometry (WKT)
        wards_csv = raw_dir / "p293-wvbd" / "2026-07-12" / "p293-wvbd.csv"
        wards_csv.parent.mkdir(parents=True, exist_ok=True)
        wards_df = pd.DataFrame({
            "ward_id": [1, 2, 3],
            "ward_name": ["Ward 1", "Ward 2", "Ward 3"],
            "geometry": [
                "POLYGON((-0.5 -0.5, 1.5 -0.5, 1.5 0.5, -0.5 0.5, -0.5 -0.5))",
                "POLYGON((-0.5 0.5, 1.5 0.5, 1.5 1.5, -0.5 1.5, -0.5 0.5))",
                "POLYGON((-0.5 1.5, 1.5 1.5, 1.5 2.5, -0.5 2.5, -0.5 1.5))"
            ],
        })
        wards_df.to_csv(wards_csv, index=False)

        # Create sample 311 CSV (no geometry)
        sr311_csv = raw_dir / "v6vf-nfxy" / "2026-07-12" / "v6vf-nfxy.csv"
        sr311_csv.parent.mkdir(parents=True, exist_ok=True)
        sr311_df = pd.DataFrame({
            "sr_id": [1001, 1002, 1003],
            "complaint_type": ["Pothole", "Street Light Out", "Pothole"],
            "ward": [1, 2, 3],
        })
        sr311_df.to_csv(sr311_csv, index=False)

        # Create manifest files
        for dataset_id in ["6imu-meau", "p293-wvbd", "v6vf-nfxy"]:
            manifest_path = raw_dir / dataset_id / "2026-07-12" / f"{dataset_id}.json"
            manifest_path.write_text('{"source_id": "%s", "acquired": true}' % dataset_id)

        return tmp_path

    def test_load_config(self, temp_project):
        """Load config/sources.yaml."""
        config = _load_config()
        assert "chicago" in config
        assert "reference_data" in config["chicago"]
        assert "street_center_lines" in config["chicago"]["reference_data"]

    def test_centerlines_csv_exists(self, temp_project):
        """Verify centerlines CSV was created."""
        centerlines_csv = Path("raw/socrata/6imu-meau/2026-07-12/6imu-meau.csv")
        assert centerlines_csv.exists()
        df = pd.read_csv(centerlines_csv)
        assert len(df) == 3
        assert "street_name" in df.columns
        assert "shape" in df.columns

    def test_wards_csv_exists(self, temp_project):
        """Verify wards CSV was created."""
        wards_csv = Path("raw/socrata/p293-wvbd/2026-07-12/p293-wvbd.csv")
        assert wards_csv.exists()
        df = pd.read_csv(wards_csv)
        assert len(df) == 3
        assert "ward_id" in df.columns
        assert "geometry" in df.columns

    def test_sr311_csv_exists(self, temp_project):
        """Verify 311 CSV was created."""
        sr311_csv = Path("raw/socrata/v6vf-nfxy/2026-07-12/v6vf-nfxy.csv")
        assert sr311_csv.exists()
        df = pd.read_csv(sr311_csv)
        assert len(df) == 3
        assert "complaint_type" in df.columns
        assert "ward" in df.columns

    @patch("holos_tools.load.HolosDB")
    def test_load_csv_with_geometry(self, mock_db_class, temp_project):
        """Test loading a CSV with geometry (GeoDataFrame path)."""
        mock_db = MagicMock()
        mock_db.connect.return_value = MagicMock()

        centerlines_csv = Path("raw/socrata/6imu-meau/2026-07-12/6imu-meau.csv")
        row_count = _load_csv_to_postgis(
            centerlines_csv, "centerlines", "ref", mock_db, geom_col="shape"
        )

        assert row_count == 3
        mock_db.load_geodataframe.assert_called_once()

    @patch("holos_tools.load.HolosDB")
    def test_load_csv_without_geometry(self, mock_db_class, temp_project):
        """Test loading a CSV without geometry (regular DataFrame path)."""
        mock_db = MagicMock()
        engine_mock = MagicMock()
        mock_db.connect.return_value = engine_mock

        sr311_csv = Path("raw/socrata/v6vf-nfxy/2026-07-12/v6vf-nfxy.csv")
        row_count = _load_csv_to_postgis(sr311_csv, "sr311", "ref", mock_db)

        assert row_count == 3

    def test_load_csv_missing_file(self, temp_project):
        """Test loading from a non-existent file."""
        from holos_tools.core import HolosDB

        db = HolosDB("postgresql://user:pass@localhost/test")
        row_count = _load_csv_to_postgis(
            Path("nonexistent.csv"), "table", "ref", db
        )
        assert row_count == 0

    @patch("holos_tools.load.HolosDB")
    def test_derived_tables_creation(self, mock_db_class, temp_project):
        """Test that derived tables (intersections, gazetteer) are created."""
        mock_db = MagicMock()

        from holos_tools.load import _create_derived_tables

        # Should not raise
        _create_derived_tables(mock_db, verbose=False)
        mock_db.execute.assert_called()

    @patch("holos_tools.load.HolosDB")
    @patch("holos_tools.load._harvest_socrata_dataset")
    def test_reference_command_success(self, mock_harvest, mock_db_class, temp_project):
        """Test holos load reference end-to-end."""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.connect.return_value = MagicMock()

        # Mock harvest to return paths to our test CSVs
        mock_harvest.side_effect = [
            Path("raw/socrata/6imu-meau/2026-07-12/6imu-meau.csv"),
            Path("raw/socrata/p293-wvbd/2026-07-12/p293-wvbd.csv"),
            Path("raw/socrata/v6vf-nfxy/2026-07-12/v6vf-nfxy.csv"),
        ]

        from typer.testing import CliRunner
        from holos_tools.load import app

        runner = CliRunner()
        result = runner.invoke(app, ["reference"])

        assert result.exit_code == 0
        assert "Reference data loading complete" in result.stdout
        assert "3 datasets" in result.stdout or "loaded_count" in result.stdout
