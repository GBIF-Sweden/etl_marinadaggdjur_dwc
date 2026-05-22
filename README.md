# etl_marinadaggdjur_dwc

Configuration-driven ETL tool for processing marine mammal observation data (e.g., harbor porpoise/tumlare, seals) into Darwin Core format for GBIF.

## Overview

This repository provides a framework for extracting data from source databases, transforming it according to configured rules, and loading it into a target database. It currently supports pipelines for:

- **Tumlare (Harbor Porpoise):** Swedish harbor porpoise observation data.
- **Seal:** Swedish seal observation data.

## Setup

Use a Python 3.12+ environment and install dependencies:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

To install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

## Running the ETL

The ETL is driven by YAML configuration files found in `etl_configs/`.

```bash
python -m tumlaretogbif.main etl_configs/tumlare.yml --env-file .env
```

### Arguments

- `config_path`: Path to the ETL configuration YAML (e.g., `etl_configs/tumlare.yml`).
- `--env-file`: Optional path to a `.env` file containing database credentials (`SOURCE_DB_*` and `TARGET_DB_*`).
- `--source-db-credentials-path`: Optional path to a JSON file with source database credentials.
- `--target-db-credentials-path`: Optional path to a JSON file with target database credentials.

## Validation

A script is provided to validate the configuration files:

```bash
python scripts/validate_configs.py
```

## Testing

Run tests using `pytest`:

```bash
pytest
```
