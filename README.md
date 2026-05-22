# etl_marinadaggdjur_dwc

Configuration-driven ETL tool for processing marine mammal observation data (e.g., harbor porpoise/tumlare, seals) into Darwin Core format for GBIF.

## Overview

This repository provides a framework for extracting data from source databases, transforming it according to configured rules, and loading it into a target database. It currently supports pipelines for:

- **Tumlare (Harbor Porpoise):** Swedish harbor porpoise observation data.
- **Seal:** Swedish seal observation data.

## Setup

### Native Python

Use a Python 3.12+ environment and install dependencies:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

To install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

### Docker

Build the Docker image:

```bash
docker build -t etl_marinadaggdjur_dwc .
```

## Running the ETL

The ETL is driven by YAML configuration files found in `etl_configs/`.

### Option 1: Native Execution (Python)

```bash
python -m marinadaggdjur.main etl_configs/tumlare.yml --env-file .env
```

### Option 2: Docker Execution

#### Using Docker Run
Ensure you have a `.env` file with the necessary credentials.

```bash
docker run --env-file .env -v $(pwd)/data:/app/data etl_marinadaggdjur_dwc python -m marinadaggdjur.main etl_configs/tumlare.yml
```

#### Using Docker Compose
Update the `env_file` path in `docker-compose.yml` if necessary, then run:

```bash
docker compose up
```

### Arguments

- `config_path`: Path to the ETL configuration YAML (e.g., `etl_configs/tumlare.yml`).
- `--env-file`: Optional path to a `.env` file containing database credentials (`SOURCE_DB_*` and `TARGET_DB_*`).

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
