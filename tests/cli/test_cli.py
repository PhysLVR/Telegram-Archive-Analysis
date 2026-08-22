"""
Tests for CLI commands.
"""

from typer.testing import CliRunner

from t_a_a.cli.main import app

runner = CliRunner()


class TestCLI:
    """Tests for CLI commands."""

    def test_version_command(self) -> None:
        """Test the version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "T_A_A version" in result.stdout
        assert "0.1.0" in result.stdout

    def test_help_command(self) -> None:
        """Test the help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Telegram Archive Analysis" in result.stdout
        assert "import" in result.stdout
        assert "validate" in result.stdout
        assert "stats" in result.stdout
        assert "analyze" in result.stdout
        assert "export" in result.stdout
        assert "inspect" in result.stdout

    def test_import_command_basic(self) -> None:
        """Test the import command with basic arguments."""
        result = runner.invoke(app, ["import", "/fake/path"])
        assert result.exit_code == 1

    def test_import_command_with_output(self) -> None:
        """Test the import command with output option."""
        result = runner.invoke(
            app, ["import", "/fake/path", "--output", "/custom/output"]
        )
        assert result.exit_code == 1

    def test_import_command_verbose(self) -> None:
        """Test the import command with verbose flag."""
        result = runner.invoke(
            app, ["import", "/fake/path", "--verbose"]
        )
        assert result.exit_code == 1

    def test_validate_command(self) -> None:
        """Test the validate command."""
        result = runner.invoke(app, ["validate", "/fake/dataset"])
        assert result.exit_code == 0
        assert "Validate command invoked" in result.stdout

    def test_stats_command(self) -> None:
        """Test the stats command."""
        result = runner.invoke(app, ["stats", "/fake/dataset"])
        assert result.exit_code == 0
        assert "Stats command invoked" in result.stdout

    def test_analyze_command(self) -> None:
        """Test the analyze command."""
        result = runner.invoke(app, ["analyze", "/fake/dataset"])
        assert result.exit_code == 0
        assert "Analyze command invoked" in result.stdout

    def test_analyze_command_with_output(self) -> None:
        """Test the analyze command with output option."""
        result = runner.invoke(
            app, ["analyze", "/fake/dataset", "--output", "/results.json"]
        )
        assert result.exit_code == 0
        assert "/results.json" in result.stdout

    def test_export_command(self) -> None:
        """Test the export command."""
        result = runner.invoke(app, ["export", "/fake/dataset"])
        assert result.exit_code == 0
        assert "Export command invoked" in result.stdout
        assert "Format: json" in result.stdout

    def test_export_command_with_format(self) -> None:
        """Test the export command with format option."""
        result = runner.invoke(
            app, ["export", "/fake/dataset", "--format", "csv"]
        )
        assert result.exit_code == 0
        assert "Format: csv" in result.stdout

    def test_inspect_command(self) -> None:
        """Test the inspect command."""
        result = runner.invoke(app, ["inspect", "/fake/dataset"])
        assert result.exit_code == 0
        assert "Inspect command invoked" in result.stdout

    def test_inspect_command_with_message_id(self) -> None:
        """Test the inspect command with message ID."""
        result = runner.invoke(
            app, ["inspect", "/fake/dataset", "--message-id", "msg123"]
        )
        assert result.exit_code == 0
        assert "msg123" in result.stdout
