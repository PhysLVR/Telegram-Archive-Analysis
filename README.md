# T_A_A - Telegram Archive Analysis

Export & Analysis of Telegram Chat

## Overview

T_A_A is a robust, modular, and extensible system for importing Telegram chat exports, normalizing their heterogeneous data, storing structured representations, and providing analytical capabilities over large chat datasets.

## Features

- **Import**: Parse Telegram HTML/JSON export files
- **Normalize**: Convert heterogeneous data into consistent internal schema
- **Store**: Persist structured data in SQLite
- **Analyze**: Generate statistics and insights
- **Export**: Output results in various formats

## Requirements

- Python 3.12+

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Show version
t-aa version

# Import a Telegram export
t-aa import <path-to-export>

# Validate a dataset
t-aa validate <dataset-path>

# Show statistics
t-aa stats <dataset-path>

# Analyze a dataset
t-aa analyze <dataset-path>

# Export results
t-aa export <dataset-path>

# Inspect dataset contents
t-aa inspect <dataset-path>
```

## Development

### Run Tests

```bash
pytest
```

### Run Linting

```bash
ruff check .
```

### Run Type Checking

```bash
mypy src/
```

## Project Structure

```
src/t_a_a/
├── parser/          # Telegram export parsing
├── models/          # Domain models
├── normalization/   # Data normalization
├── processing/      # Data transformations
├── analysis/        # Analytics engine
├── storage/         # Persistence layer
├── export/          # Export generators
├── cli/             # Command-line interface
└── utils/           # Utilities
```

## License

MIT
