"""
CLI entry point for T_A_A.

Provides command-line interface commands for importing, validating,
analyzing, and exporting Telegram chat data.
"""


import typer

app = typer.Typer(
    name="t-aa",
    help="Telegram Archive Analysis - Import and analyze Telegram chat exports",
    add_completion=False,
)


@app.command()
def version() -> None:
    """Show the version of T_A_A."""
    from t_a_a import __version__

    typer.echo(f"T_A_A version {__version__}")


@app.command("import")
def import_data(
    path: str = typer.Argument(..., help="Path to Telegram export directory or file"),
    output: str = typer.Option(
        "data/processed",
        "--output", "-o",
        help="Output directory for processed data",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose output",
    ),
) -> None:
    """
    Import a Telegram chat export.

    Discovers and parses Telegram export files, normalizes the data,
    and writes an import summary to the specified output directory.

    Note: Full persistent storage (SQLite) is not yet implemented; this
    command currently parses, aggregates statistics, and saves a JSON
    summary. Persistent storage will land in a later sprint.
    """
    import json
    import logging
    from pathlib import Path

    from t_a_a.parser import (
        ImportResult,
        discover_export,
        parse_export_files,
    )
    from t_a_a.utils.logging_config import get_logger

    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logger = get_logger(__name__, level=log_level)

    try:
        # Step 1: Discover export files
        logger.info(f"Discovering export files in: {path}")
        discovery_result = discover_export(path)

        files_processed = len(discovery_result.discovered_files)
        logger.info(f"Found {files_processed} HTML file(s)")
        for warning in discovery_result.warnings:
            logger.warning(warning)

        if files_processed == 0:
            typer.echo("No HTML export files found.", err=True)
            raise SystemExit(1)

        # Step 2: Parse files and collect results
        # All timestamps from the parser are timezone-aware, so comparisons
        # across files (mixed real-TZ and legacy fixtures) are safe.
        messages_parsed = 0
        messages_skipped = 0
        participants: set[str] = set()
        service_messages = 0
        attachments_found = 0
        links_found = 0
        earliest_timestamp = None
        latest_timestamp = None

        for message, chat_info, current_participants in parse_export_files(
            discovery_result.discovered_files
        ):
            if message is None:
                messages_skipped += 1
                continue

            messages_parsed += 1

            if message.sender_display_name:
                participants.add(message.sender_display_name)

            if message.message_type == "service":
                service_messages += 1

            attachments_found += len(message.attachments)
            links_found += len(message.links)

            if message.timestamp is not None:
                if earliest_timestamp is None or message.timestamp < earliest_timestamp:
                    earliest_timestamp = message.timestamp
                if latest_timestamp is None or message.timestamp > latest_timestamp:
                    latest_timestamp = message.timestamp

        result = ImportResult(
            input_path=path,
            files_processed=files_processed,
            messages_parsed=messages_parsed,
            messages_skipped=messages_skipped,
            participants_discovered=len(participants),
            service_messages=service_messages,
            attachments_found=attachments_found,
            links_found=links_found,
            warnings_count=len(discovery_result.warnings),
            errors_count=0,
            earliest_timestamp=earliest_timestamp,
            latest_timestamp=latest_timestamp,
        )

        # Step 3: Write import summary (storage layer not yet implemented)
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "import_summary.json"
        summary_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        logger.info(f"Import summary written to: {summary_path}")

        # Report results
        typer.echo("\n=== Import Complete ===")
        typer.echo(f"Input: {path}")
        typer.echo(f"Files processed: {result.files_processed}")
        typer.echo(f"Messages parsed: {result.messages_parsed}")
        typer.echo(f"Messages skipped: {result.messages_skipped}")
        typer.echo(f"Participants: {result.participants_discovered}")
        typer.echo(f"Service messages: {result.service_messages}")
        typer.echo(f"Attachments: {result.attachments_found}")
        typer.echo(f"Links: {result.links_found}")

        if result.earliest_timestamp:
            typer.echo(f"Earliest message: {result.earliest_timestamp}")
        if result.latest_timestamp:
            typer.echo(f"Latest message: {result.latest_timestamp}")

        typer.echo(f"Summary: {summary_path}")

        if not result.success:
            typer.echo("\n⚠️  Import completed with issues")
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Import failed: {e}")
        typer.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def validate(
    dataset: str = typer.Argument(..., help="Path to dataset to validate"),
) -> None:
    """
    Validate a dataset for integrity and completeness.

    Checks for missing fields, inconsistent data, and potential issues.
    """
    # TODO: Implement validation logic
    typer.echo(f"Validate command invoked with dataset: {dataset}")


@app.command()
def stats(
    dataset: str = typer.Argument(..., help="Path to dataset to analyze"),
) -> None:
    """
    Show basic statistics for a dataset.

    Displays message counts, participant counts, and activity summaries.
    """
    # TODO: Implement statistics logic
    typer.echo(f"Stats command invoked with dataset: {dataset}")


@app.command()
def analyze(
    dataset: str = typer.Argument(..., help="Path to dataset to analyze"),
    output: str | None = typer.Option(
        None,
        "--output", "-o",
        help="Output file for analysis results",
    ),
) -> None:
    """
    Perform detailed analysis on a dataset.

    Generates comprehensive analytical reports including temporal,
    participant, and content analysis.
    """
    # TODO: Implement analysis logic
    typer.echo(f"Analyze command invoked with dataset: {dataset}")
    if output:
        typer.echo(f"Results will be written to: {output}")


@app.command("export")
def export_data(
    dataset: str = typer.Argument(..., help="Path to dataset to export"),
    format: str = typer.Option(
        "json",
        "--format", "-f",
        help="Export format (json, csv)",
    ),
    output: str = typer.Option(
        "data/export",
        "--output", "-o",
        help="Output directory for exported data",
    ),
) -> None:
    """
    Export analyzed data to various formats.

    Supports JSON, CSV, and other machine-readable formats.
    """
    # TODO: Implement export logic
    typer.echo(f"Export command invoked with dataset: {dataset}")
    typer.echo(f"Format: {format}")
    typer.echo(f"Output directory: {output}")


@app.command()
def inspect(
    dataset: str = typer.Argument(..., help="Path to dataset to inspect"),
    message_id: str | None = typer.Option(
        None,
        "--message-id", "-m",
        help="Inspect a specific message by ID",
    ),
) -> None:
    """
    Inspect dataset contents interactively.

    Allows detailed inspection of messages, participants, and metadata.
    """
    # TODO: Implement inspect logic
    typer.echo(f"Inspect command invoked with dataset: {dataset}")
    if message_id:
        typer.echo(f"Looking for message ID: {message_id}")


if __name__ == "__main__":
    app()
