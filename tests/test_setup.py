"""Test basic infrastructure setup."""

import pytest
from pathlib import Path
from holos_tools.core import Config
from holos_tools.cli import app


def test_config_loads():
    """Verify config loads from YAML and .env."""
    config = Config()
    assert config.get("db.host") is not None
    assert config.api_key_anthropic is not None


def test_cli_version():
    """Verify holos version command works."""
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "holos" in result.stdout


def test_harvest_help():
    """Verify harvest subcommand exists."""
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["harvest", "--help"])
    assert result.exit_code == 0
    assert "Harvest" in result.stdout


def test_extract_help():
    """Verify extract subcommand exists."""
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["extract", "--help"])
    assert result.exit_code == 0
    assert "Extract" in result.stdout


def test_git_repository():
    """Verify repo is initialized with git."""
    git_dir = Path(".git")
    assert git_dir.exists(), "Repository must be initialized with git"


def test_schema_files_exist():
    """Verify schema and config files are present."""
    files = [
        Path("db/init/001-init-schema.sql"),
        Path("config/sources.yaml"),
        Path("config/geocode.yaml"),
        Path("config/vocabularies.yaml"),
        Path("schemas/agent_output.schema.json"),
    ]
    for f in files:
        assert f.exists(), f"Expected {f} to exist"


def test_agent_definitions_exist():
    """Verify agent definitions are present."""
    agents = [
        Path(".claude/agents/harvester.md"),
        Path(".claude/agents/extractor.md"),
        Path(".claude/agents/geolocator.md"),
        Path(".claude/agents/verifier.md"),
        Path(".claude/agents/normalizer.md"),
    ]
    for agent in agents:
        assert agent.exists(), f"Expected agent {agent} to exist"
