import json
import logging
import os
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import yaml

from marinadaggdjur.transformation.transform import get_registered_transformations

REQUIRED_TOP_LEVEL_KEYS = ("extract", "mapping", "defaults", "transformations", "load")
REQUIRED_EXTRACT_KEYS = ("database_hostname", "database_name", "database_port", "sql_file")
REQUIRED_LOAD_KEYS = ("database_hostname", "database_name", "database_port", "database_table")


def _require_mapping(value, label):
    if not isinstance(value, Mapping):
        raise ValueError(f"Configuration section '{label}' must be a mapping.")
    return value


def _require_string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configuration value '{label}' must be a non-empty string.")


def _require_int_like(value, label):
    try:
        int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Configuration value '{label}' must be an integer.") from exc


def _require_positive_int(value, label):
    _require_int_like(value, label)
    if int(value) <= 0:
        raise ValueError(f"Configuration value '{label}' must be greater than zero.")


def _validate_transformations(transformations):
    if not isinstance(transformations, list):
        raise ValueError("Configuration key 'transformations' must be a list.")

    registered_transformations = get_registered_transformations()
    unknown_transformations = []
    for index, transformation in enumerate(transformations):
        if not isinstance(transformation, Mapping):
            raise ValueError(f"Transformation at index {index} must be a mapping.")

        func_name = transformation.get("function")
        if not isinstance(func_name, str) or not func_name.strip():
            raise ValueError(f"Transformation at index {index} must define a function name.")

        params = transformation.get("params", {})
        if not isinstance(params, Mapping):
            raise ValueError(f"Transformation '{func_name}' params must be a mapping.")

        if func_name not in registered_transformations:
            unknown_transformations.append(func_name)

    if unknown_transformations:
        raise ValueError(
            "Configuration contains unknown transformations: " + ", ".join(sorted(unknown_transformations))
        )


def load_db_credentials(env_prefix):
    if not env_prefix:
        raise ValueError("env_prefix is required.")

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
            f"Missing database credentials for {env_prefix}. Set env vars: "
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
    _require_mapping(config, "root")

    missing_keys = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in config]
    if missing_keys:
        raise ValueError(f"Configuration is missing required keys: {', '.join(missing_keys)}")

    extract_config = _require_mapping(config["extract"], "extract")
    load_config = _require_mapping(config["load"], "load")
    mapping_config = _require_mapping(config["mapping"], "mapping")
    defaults_config = _require_mapping(config["defaults"], "defaults")

    missing_extract_keys = [key for key in REQUIRED_EXTRACT_KEYS if key not in extract_config]
    if missing_extract_keys:
        raise ValueError(f"Extract config is missing required keys: {', '.join(missing_extract_keys)}")

    missing_load_keys = [key for key in REQUIRED_LOAD_KEYS if key not in load_config]
    if missing_load_keys:
        raise ValueError(f"Load config is missing required keys: {', '.join(missing_load_keys)}")

    _require_string(extract_config["database_hostname"], "extract.database_hostname")
    _require_string(extract_config["database_name"], "extract.database_name")
    _require_string(extract_config["sql_file"], "extract.sql_file")
    _require_int_like(extract_config["database_port"], "extract.database_port")

    _require_string(load_config["database_hostname"], "load.database_hostname")
    _require_string(load_config["database_name"], "load.database_name")
    _require_string(load_config["database_table"], "load.database_table")
    _require_int_like(load_config["database_port"], "load.database_port")

    if "batch_size" in extract_config:
        _require_positive_int(extract_config["batch_size"], "extract.batch_size")
    if "batch_size" in load_config:
        _require_positive_int(load_config["batch_size"], "load.batch_size")

    if not isinstance(mapping_config, Mapping):
        raise ValueError("Configuration key 'mapping' must be a mapping.")
    if not isinstance(defaults_config, Mapping):
        raise ValueError("Configuration key 'defaults' must be a mapping.")

    if "columns_to_dynamicproperties" in config and not isinstance(
        config["columns_to_dynamicproperties"], list
    ):
        raise ValueError("Configuration key 'columns_to_dynamicproperties' must be a list.")
    if "columns_to_dynamicproperties" in config:
        for index, column_name in enumerate(config["columns_to_dynamicproperties"]):
            if not isinstance(column_name, str) or not column_name.strip():
                raise ValueError(
                    f"Configuration value 'columns_to_dynamicproperties[{index}]' must be a non-empty string."
                )

    if "vernacular_to_scientificName" in config:
        vernacular_map = _require_mapping(
            config["vernacular_to_scientificName"], "vernacular_to_scientificName"
        )
        for vernacular, species_info in vernacular_map.items():
            _require_mapping(species_info, f"vernacular_to_scientificName.{vernacular}")
            if "scientificName" not in species_info or "taxonRank" not in species_info:
                raise ValueError(
                    "Each vernacular_to_scientificName entry must define scientificName and taxonRank."
                )
            _require_string(
                species_info["scientificName"],
                f"vernacular_to_scientificName.{vernacular}.scientificName",
            )
            _require_string(
                species_info["taxonRank"], f"vernacular_to_scientificName.{vernacular}.taxonRank"
            )

    _validate_transformations(config["transformations"])


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
