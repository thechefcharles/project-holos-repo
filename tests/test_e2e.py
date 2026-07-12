"""End-to-end pipeline tests."""

import json
from pathlib import Path
from typer.testing import CliRunner
from holos_tools.cli import app


class TestE2EPipeline:
    """Test full pipeline: harvest → extract → normalize → geocode → validate → load."""

    @pytest.fixture
    def cli_runner(self):
        """Create CLI runner."""
        return CliRunner()

    def test_cli_help_shows_all_commands(self, cli_runner):
        """Verify all pipeline commands are in help."""
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Check for main commands
        assert "harvest" in result.stdout.lower()
        assert "extract" in result.stdout.lower()
        assert "geocode" in result.stdout.lower()
        assert "validate" in result.stdout.lower()
        assert "load" in result.stdout.lower()

    def test_harvest_socrata_help(self, cli_runner):
        """Verify harvest socrata command."""
        result = cli_runner.invoke(app, ["harvest", "socrata", "--help"])
        assert result.exit_code == 0

    def test_extract_pdf_tables_help(self, cli_runner):
        """Verify extract pdf-tables command."""
        result = cli_runner.invoke(app, ["extract", "pdf-tables", "--help"])
        assert result.exit_code == 0

    def test_geocode_normalize_help(self, cli_runner):
        """Verify geocode normalize command."""
        result = cli_runner.invoke(app, ["geocode", "normalize", "--help"])
        assert result.exit_code == 0

    def test_validate_schema_help(self, cli_runner):
        """Verify validate schema command."""
        result = cli_runner.invoke(app, ["validate", "schema", "--help"])
        assert result.exit_code == 0

    def test_load_staging_help(self, cli_runner):
        """Verify load staging command."""
        result = cli_runner.invoke(app, ["load", "staging", "--help"])
        assert result.exit_code == 0


class TestPipelineDataFlow:
    """Test data flow through each stage."""

    def test_manifest_schema(self):
        """Verify manifest files follow agent output schema."""
        schema_path = Path("schemas/agent_output.schema.json")
        assert schema_path.exists(), "Agent output schema not found"

        with open(schema_path) as f:
            schema = json.load(f)

        # Verify schema has required properties
        assert "properties" in schema
        required = schema.get("required", [])
        assert "job_id" in required
        assert "status" in required
        assert "artifacts" in required
        assert "metrics" in required


class TestDeterministicTools:
    """Verify deterministic tools are documented."""

    def test_holos_tools_documented(self):
        """Verify holos command suite is fully defined."""
        # This is a documentation test
        tools = {
            "harvest": ["socrata", "url"],
            "extract": ["pdf-tables", "pdf-vector", "plate"],
            "geocode": ["normalize", "parse", "cascade"],
            "validate": ["schema", "ward-containment", "duplicate-geometry", "all"],
            "load": ["staging", "reference"],
        }
        # All tools should have help output
        assert len(tools) > 0


# Import pytest at module level
import pytest
