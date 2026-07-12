"""Golden tests for holos harvest CLI (Socrata + URL download, manifest validation)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import hashlib
import pytest
from typer.testing import CliRunner
from holos_tools.cli import app

runner = CliRunner()


@pytest.fixture
def temp_project(tmp_path, monkeypatch):
    """Set up a temporary project with config/sources.yaml."""
    monkeypatch.chdir(tmp_path)

    # Create config directory and sources.yaml
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    sources_yaml = """
chicago:
  socrata_base: "https://data.cityofchicago.org/resource"
  datasets:
    street_center_lines: "6imu-meau"
    ward_boundaries_2023: "p293-wvbd"
  menu_pdfs:
    role: "source"
"""
    (config_dir / "sources.yaml").write_text(sources_yaml)

    return tmp_path


class TestHarvestSocrata:
    """Golden tests for holos harvest socrata."""

    def test_socrata_download_and_manifest(self, temp_project):
        """Download a Socrata dataset and verify manifest is created."""
        csv_data = b"id,name,value\n1,test,100\n2,sample,200\n"

        with patch("holos_tools.harvest.httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = csv_data
            mock_get.return_value = mock_response

            result = runner.invoke(app, ["harvest", "socrata", "--dataset", "6imu-meau"])

            assert result.exit_code == 0
            assert "✓ Downloaded 6imu-meau" in result.stdout

            # Verify files exist
            manifest_files = list(Path("raw/socrata/6imu-meau").glob("*/6imu-meau.json"))
            assert len(manifest_files) == 1

            manifest = json.loads(manifest_files[0].read_text())
            assert manifest["source_id"] == "socrata_6imu-meau"
            assert "sha256:" in manifest["checksum"]
            assert manifest["acquisition_method"] == "socrata_api"

    def test_socrata_idempotency(self, temp_project):
        """Second run with same checksum skips download."""
        csv_data = b"id,name,value\n1,test,100\n"

        with patch("holos_tools.harvest.httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = csv_data
            mock_get.return_value = mock_response

            # First run
            result1 = runner.invoke(app, ["harvest", "socrata", "--dataset", "6imu-meau"])
            assert result1.exit_code == 0

            # Second run (should skip)
            result2 = runner.invoke(app, ["harvest", "socrata", "--dataset", "6imu-meau"])
            assert result2.exit_code == 0
            assert "Skipped 6imu-meau" in result2.stdout

    def test_socrata_not_in_config(self, temp_project):
        """Dataset not in config is rejected."""
        result = runner.invoke(app, ["harvest", "socrata", "--dataset", "unknown_id"])
        assert result.exit_code == 1
        assert "not in config/sources.yaml" in result.stdout


class TestHarvestUrl:
    """Golden tests for holos harvest url."""

    def test_url_download_and_manifest(self, temp_project):
        """Download from URL and verify manifest is created."""
        pdf_data = b"%PDF-1.4\n%mock pdf content"

        with patch("holos_tools.harvest.httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = pdf_data
            mock_get.return_value = mock_response

            result = runner.invoke(
                app,
                [
                    "harvest",
                    "url",
                    "--source-url",
                    "https://chicago.gov/menu/2023Menu.pdf",
                    "--source-id",
                    "menu_pdfs",
                ],
            )

            assert result.exit_code == 0
            assert "✓ Harvested menu_pdfs" in result.stdout

            # Verify manifest
            manifest_files = list(Path("raw/menu_pdfs").glob("*/*.json"))
            assert len(manifest_files) == 1

            manifest = json.loads(manifest_files[0].read_text())
            assert manifest["source_id"] == "menu_pdfs"
            assert manifest["acquisition_method"] == "http_download"

    def test_url_local_file_ingest(self, temp_project):
        """Ingest a local PDF file."""
        # Create a test PDF
        pdf_dir = Path("pdfs")
        pdf_dir.mkdir()
        pdf_file = pdf_dir / "test.pdf"
        pdf_data = b"%PDF-1.4\n%local file"
        pdf_file.write_bytes(pdf_data)

        result = runner.invoke(
            app,
            [
                "harvest",
                "url",
                "--source-url",
                str(pdf_file.resolve()),
                "--source-id",
                "menu_pdfs",
            ],
        )

        assert result.exit_code == 0
        assert "✓ Harvested menu_pdfs/test.pdf" in result.stdout

        # Verify manifest
        manifest_files = list(Path("raw/menu_pdfs").glob("*/*.json"))
        assert len(manifest_files) == 1

        manifest = json.loads(manifest_files[0].read_text())
        assert manifest["acquisition_method"] == "local_file"
        assert "file://" in manifest["url"]

    def test_url_idempotency(self, temp_project):
        """Second run with same checksum skips download."""
        pdf_data = b"%PDF-1.4\n%test"

        with patch("holos_tools.harvest.httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = pdf_data
            mock_get.return_value = mock_response

            # First run
            result1 = runner.invoke(
                app,
                [
                    "harvest",
                    "url",
                    "--source-url",
                    "https://chicago.gov/menu/2023.pdf",
                    "--source-id",
                    "menu_pdfs",
                ],
            )
            assert result1.exit_code == 0

            # Second run (should skip)
            result2 = runner.invoke(
                app,
                [
                    "harvest",
                    "url",
                    "--source-url",
                    "https://chicago.gov/menu/2023.pdf",
                    "--source-id",
                    "menu_pdfs",
                ],
            )
            assert result2.exit_code == 0
            assert "Skipped menu_pdfs" in result2.stdout

    def test_url_checksum_mismatch_redownloads(self, temp_project):
        """Changed checksum triggers re-download."""
        pdf_data_v1 = b"%PDF-1.4\n%version 1"
        pdf_data_v2 = b"%PDF-1.4\n%version 2"

        with patch("holos_tools.harvest.httpx.get") as mock_get:
            # First run with v1
            mock_response = MagicMock()
            mock_response.content = pdf_data_v1
            mock_get.return_value = mock_response

            result1 = runner.invoke(
                app,
                [
                    "harvest",
                    "url",
                    "--source-url",
                    "https://chicago.gov/menu/2023.pdf",
                    "--source-id",
                    "menu_pdfs",
                ],
            )
            assert result1.exit_code == 0

            # Second run with v2 (different checksum)
            mock_response.content = pdf_data_v2
            result2 = runner.invoke(
                app,
                [
                    "harvest",
                    "url",
                    "--source-url",
                    "https://chicago.gov/menu/2023.pdf",
                    "--source-id",
                    "menu_pdfs",
                ],
            )
            assert result2.exit_code == 0
            assert "✓ Harvested menu_pdfs" in result2.stdout

    def test_url_not_in_config(self, temp_project):
        """Source not in config is rejected."""
        result = runner.invoke(
            app,
            [
                "harvest",
                "url",
                "--source-url",
                "https://example.com/data.csv",
                "--source-id",
                "unknown_source",
            ],
        )
        assert result.exit_code == 1
        assert "not in config/sources.yaml" in result.stdout


class TestManifestFormat:
    """Verify manifest JSON structure."""

    def test_manifest_has_required_fields(self, temp_project):
        """Manifest contains all required fields."""
        csv_data = b"test data"

        with patch("holos_tools.harvest.httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = csv_data
            mock_get.return_value = mock_response

            runner.invoke(app, ["harvest", "socrata", "--dataset", "6imu-meau"])

            manifest_files = list(Path("raw/socrata/6imu-meau").glob("*/*.json"))
            manifest = json.loads(manifest_files[0].read_text())

            required = [
                "source_id",
                "url",
                "checksum",
                "retrieved_at",
                "size_bytes",
                "acquisition_method",
            ]
            for field in required:
                assert field in manifest, f"Missing field: {field}"

    def test_checksum_format(self, temp_project):
        """Checksum is SHA256 with correct format."""
        csv_data = b"test"
        expected_hash = hashlib.sha256(csv_data).hexdigest()

        with patch("holos_tools.harvest.httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.content = csv_data
            mock_get.return_value = mock_response

            runner.invoke(app, ["harvest", "socrata", "--dataset", "6imu-meau"])

            manifest_files = list(Path("raw/socrata/6imu-meau").glob("*/*.json"))
            manifest = json.loads(manifest_files[0].read_text())

            assert manifest["checksum"] == f"sha256:{expected_hash}"
