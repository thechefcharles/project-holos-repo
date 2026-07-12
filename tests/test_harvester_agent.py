"""Golden tests for the Harvester agent (orchestration + structured output)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Import the agent
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from holos_tools.harvest.agent import (
    load_config,
    run_harvest_socrata,
    run_harvest_url,
    discover_reference_layers,
    discover_menu_pdfs,
    build_agent_output,
    main,
)


class TestHarvesterAgentOrchestration:
    """Golden tests for harvester agent workflow."""

    @pytest.fixture
    def temp_project(self, tmp_path, monkeypatch):
        """Set up a temporary project with config/sources.yaml."""
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
  menu_pdfs:
    tier: "public"
    rights: "public-record"
    status: "in_hand"
    role: "menu spending"
    url_patterns:
      - "general/CIP/CIPDocs/AldermanicMenuPostings/{YEAR}Menu.pdf"
      - "supp_info/CIP_Archive/Aldermanic Menu/Quarterly Menu Reports Q{N} {YEAR}.pdf"
ward_wise:
  tier: "public"
  rights: "public-record"
  status: "in_hand"
  api: "https://www.wardwisechicago.org/api/spendingitems"
  role: "answer-key benchmark"
"""
        (config_dir / "sources.yaml").write_text(sources_yaml)

        return tmp_path

    def test_discover_reference_layers(self, temp_project):
        """Discover all reference layers from config."""
        config = load_config()
        layers = discover_reference_layers(config)

        assert len(layers) == 2
        assert layers[0]["dataset_id"] == "6imu-meau"
        assert layers[1]["dataset_id"] == "p293-wvbd"
        assert all(layer["type"] == "socrata" for layer in layers)

    def test_discover_menu_pdfs(self, temp_project):
        """Discover menu PDF source patterns."""
        config = load_config()
        sources = discover_menu_pdfs(config)

        assert len(sources) == 2
        assert all(source["source_id"] == "menu_pdfs" for source in sources)
        assert "{YEAR}" in sources[0]["source_url"]
        assert "{N}" in sources[1]["source_url"]

    def test_build_agent_output_success(self):
        """Verify agent output JSON structure."""
        output = build_agent_output(
            job_id="test-job-123",
            status="success",
            artifacts=[{"path": "raw/test.json", "checksum": "sha256:abc123"}],
            metrics={"sources_discovered": 1, "bytes_downloaded": 1000},
            flags=[],
            needs_human=False,
            reasons=["Test reason"],
        )

        # Verify required fields per schemas/agent_output.schema.json
        assert "job_id" in output
        assert output["status"] == "success"
        assert isinstance(output["artifacts"], list)
        assert isinstance(output["metrics"], dict)
        assert isinstance(output["flags"], list)
        assert isinstance(output["needs_human"], bool)
        assert isinstance(output["reasons"], list)

    def test_build_agent_output_needs_human(self):
        """Verify agent can flag needs_human."""
        output = build_agent_output(
            job_id="test-job-456",
            status="success",
            artifacts=[],
            metrics={},
            flags=["new_format_detected"],
            needs_human=True,
            reasons=["Found new PDF format not in patterns"],
        )

        assert output["needs_human"] is True
        assert "new_format_detected" in output["flags"]

    @patch("holos_tools.harvest.agent.subprocess.run")
    def test_harvest_socrata_cli_success(self, mock_run):
        """Test successful Socrata harvest."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="✓ Downloaded 6imu-meau → raw/socrata/6imu-meau/2026-07-12/6imu-meau.csv",
            stderr="",
        )

        result = run_harvest_socrata("6imu-meau")

        assert result["status"] == "success"
        assert result["dataset_id"] == "6imu-meau"
        mock_run.assert_called_once()

    @patch("holos_tools.harvest.agent.subprocess.run")
    def test_harvest_url_cli_success(self, mock_run):
        """Test successful URL harvest."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="✓ Harvested menu_pdfs/2023Menu.pdf → raw/menu_pdfs/2026-07-12/2023Menu.pdf",
            stderr="",
        )

        result = run_harvest_url(
            "https://chicago.gov/menu/2023Menu.pdf",
            "menu_pdfs"
        )

        assert result["status"] == "success"
        assert result["source_id"] == "menu_pdfs"

    @patch("holos_tools.harvest.agent.subprocess.run")
    def test_harvest_cli_failure(self, mock_run):
        """Test CLI failure handling."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Connection failed",
        )

        result = run_harvest_socrata("unknown_id")

        assert result["status"] == "failed"
        assert "Connection failed" in result["error"]

    def test_agent_output_schema_compliance(self, temp_project):
        """Verify agent output is compliant with agent_output.schema.json."""
        # Create minimal raw/socrata structure for the agent to find
        raw_dir = Path("raw/socrata/6imu-meau/2026-07-12")
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Create a mock manifest
        manifest = {
            "source_id": "socrata_6imu-meau",
            "url": "https://data.cityofchicago.org/api/views/6imu-meau/rows.csv",
            "checksum": "sha256:test123",
            "retrieved_at": "2026-07-12T00:00:00",
            "size_bytes": 5000,
            "acquisition_method": "socrata_api",
        }
        (raw_dir / "6imu-meau.json").write_text(json.dumps(manifest))

        with patch("holos_tools.harvest.agent.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="✓ Downloaded", stderr="")

            output = main()

            # Verify structure per schemas/agent_output.schema.json
            assert "job_id" in output
            assert output["status"] in ["success", "failed"]
            assert "artifacts" in output
            assert "metrics" in output
            assert "flags" in output
            assert "needs_human" in output
            assert "reasons" in output

            # Verify metrics are populated
            assert output["metrics"]["sources_discovered"] >= 0
            assert output["metrics"]["bytes_downloaded"] >= 0
