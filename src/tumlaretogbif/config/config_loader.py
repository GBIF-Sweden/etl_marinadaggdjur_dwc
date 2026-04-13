import json
import logging
import os
from copy import deepcopy
from pathlib import Path

import yaml

from tumlaretogbif.transformation.transform import get_registered_transformations


def load_db_credentials(config_path=None, env_prefix=None):
    if config_path:
        return load_config_file(config_path)

    if not env_prefix:
        raise ValueError("env_prefix is required when config_path is not provided.")

    user = os.getenv(f"{env_prefix}_DB_USER")
    password = os.getenv(f"{env_prefix}_DB_PASSWORD")

    missing = [
        env_var
        for env_var, value in {
            f"{env_prefix}_DB_USER": user,
            f"{env_prefix}_DB_PASSWORD": password,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing database credentials. Provide a credentials JSON file or set env vars: "
            + ", ".join(missing)
        )

    return {
        "database_user": user,
        "database_password": password,
    }


def load_env_file(env_file_path):
    env_path = Path(env_file_path)
    if not env_path.exists():
        raise FileNotFoundError(f"Environment file not found at {env_file_path}.")

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError(f"Invalid environment variable line in {env_file_path}: {line}")
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def validate_etl_config(config):
    required_top_level_keys = ["extract", "mapping", "defaults", "transformations", "load"]
    missing_keys = [key for key in required_top_level_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Configuration is missing required keys: {', '.join(missing_keys)}")

    extract_required_keys = ["database_hostname", "database_name", "database_port", "sql_file"]
    load_required_keys = ["database_hostname", "database_name", "database_port", "database_table"]

    missing_extract_keys = [key for key in extract_required_keys if key not in config["extract"]]
    if missing_extract_keys:
        raise ValueError(f"Extract config is missing required keys: {', '.join(missing_extract_keys)}")

    missing_load_keys = [key for key in load_required_keys if key not in config["load"]]
    if missing_load_keys:
        raise ValueError(f"Load config is missing required keys: {', '.join(missing_load_keys)}")

    if not isinstance(config["transformations"], list):
        raise ValueError("Configuration key 'transformations' must be a list.")

    registered_transformations = get_registered_transformations()
    unknown_transformations = sorted(
        transformation.get("function")
        for transformation in config["transformations"]
        if transformation.get("function") not in registered_transformations
    )
    if unknown_transformations:
        raise ValueError(
            "Configuration contains unknown transformations: "
            + ", ".join(unknown_transformations)
        )


def normalize_config_deprecations(config):
    normalized = deepcopy(config)
    load_config = normalized.get("load", {})
    legacy_output_path = load_config.pop("targeFilePath", None)
    if legacy_output_path is not None and "targetFilePath" not in load_config:
        logging.warning(
            "Config key 'targeFilePath' is deprecated; use 'targetFilePath' instead."
        )
        load_config["targetFilePath"] = legacy_output_path
    normalized["load"] = load_config
    return normalized


def load_config_file(config_path):
    config_path = Path(config_path)
    try:
        with config_path.open("r", encoding="utf-8") as file:
            if config_path.suffix in {".yml", ".yaml"}:
                data = yaml.safe_load(file)
                if data is None:
                    raise ValueError(f"Configuration file is empty: {config_path}")
                return normalize_config_deprecations(data)
            return normalize_config_deprecations(json.load(file))
    except FileNotFoundError:
        logging.exception(f"Error: Configuration file not found at {config_path}.")
        raise
    except yaml.YAMLError:
        logging.exception("Error: Failed to decode YAML from the configuration file.")
        raise
    except json.JSONDecodeError:
        logging.exception("Error: Failed to decode JSON from the configuration file.")
        raise


def load_json_config(config_path):
    return load_config_file(config_path)
