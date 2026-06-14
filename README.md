# etl_marinadaggdjur_dwc

Configuration-driven ETL tool for processing marine mammal observation data (e.g., harbor porpoise/tumlare, seals) into Darwin Core format for GBIF.

## Overview

This repository provides a framework for extracting data from source databases, transforming it according to configured rules, and loading it into a target database. It currently supports pipelines for:

- **Tumlare (Harbor Porpoise):** Swedish harbor porpoise observation data.
- **Seal:** Swedish seal observation data.

## Setup

### Local Development

Use Python 3.12+ and the repository's virtual environment:

```bash
python -m venv .venv
./.venv/bin/python -m pip install -e '.[dev]'
```

This installs the application, runtime dependencies, and development tools declared in `pyproject.toml`.

### Docker

Build the Docker image:

```bash
docker build -t etl_marinadaggdjur_dwc .
```

## Running the ETL

The ETL is driven by YAML configuration files found in `etl_configs/`.

### Native execution

```bash
./.venv/bin/python -m marinadaggdjur etl_configs/tumlare.yml --env-file .env
```

You can also use the console script after installing the project:

```bash
./.venv/bin/marinadaggdjur etl_configs/tumlare.yml --env-file .env
```

### Docker execution

Ensure you have a `.env` file with the necessary credentials.

```bash
docker run --env-file .env -v $(pwd)/data:/app/data etl_marinadaggdjur_dwc python -m marinadaggdjur etl_configs/tumlare.yml
```

Using Docker Compose:

```bash
docker compose up
```

The current `docker-compose.yml` expects the image `etl_marinadaggdjur_dwc:latest` to be available locally. If you prefer Compose to build the image itself, uncomment the `build` section in that file.

### Arguments

- `config_path`: Path to the ETL configuration YAML (e.g., `etl_configs/tumlare.yml`).
- `--env-file`: Optional path to a `.env` file containing database credentials (`SOURCE_DB_*` and `TARGET_DB_*`).

### Environment variables

The ETL reads the following variables:

- `SOURCE_DB_USER`
- `SOURCE_DB_PASSWORD`
- `TARGET_DB_USER`
- `TARGET_DB_PASSWORD`
- `LOG_LEVEL` for application logging, default `INFO`
- `LOG_FILE` for optional file logging

`RUN_ID` and `CONFIG_NAME` are set automatically during each run and are included in structured logs.

## Validation

Validate all repo configs and referenced SQL files:

```bash
./.venv/bin/python -m scripts.validate_configs
```

## Testing

Run tests using `pytest`:

```bash
./.venv/bin/python -m pytest
```

## Quality Checks

The repository includes the following common maintenance commands:

```bash
make validate-configs
make lint
make test
make ci
```

`make ci` runs config validation, linting, and tests. `make release-check` also builds the Docker image.

## Configuration Notes

- ETL behavior is controlled by YAML files in `etl_configs/`.
- Transformation names must match registered functions in `src/marinadaggdjur/transformation/transform.py`.
- Config validation now checks section types, required keys, transformation parameters, and known legacy fields.
- Retry behavior for database writes uses exponential backoff with jitter.
