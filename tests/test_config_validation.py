import os
from pathlib import Path

import pytest

from tumlaretogbif.config.config_loader import (
    load_config_file,
    load_db_credentials,
    load_env_file,
    validate_etl_config,
)


def test_validate_all_repo_configs():
    config_dir = Path("etl_configs")
    for config_path in sorted(
        [*config_dir.glob("*.yml"), *config_dir.glob("*.yaml")]
    ):
        config = load_config_file(config_path)
        validate_etl_config(config)


def test_load_db_credentials_from_environment(monkeypatch):
    monkeypatch.setenv("SOURCE_DB_USER", "user")
    monkeypatch.setenv("SOURCE_DB_PASSWORD", "password")

    credentials = load_db_credentials(env_prefix="SOURCE")

    assert credentials == {
        "database_user": "user",
        "database_password": "password",
    }


def test_load_db_credentials_raises_for_missing_env(monkeypatch):
    monkeypatch.delenv("SOURCE_DB_USER", raising=False)
    monkeypatch.delenv("SOURCE_DB_PASSWORD", raising=False)

    with pytest.raises(ValueError):
        load_db_credentials(env_prefix="SOURCE")


def test_load_env_file_sets_missing_values(tmp_path, monkeypatch):
    monkeypatch.delenv("SOURCE_DB_USER", raising=False)
    monkeypatch.delenv("TARGET_DB_PASSWORD", raising=False)
    env_file = tmp_path / "local.env"
    env_file.write_text(
        "SOURCE_DB_USER=test-user\nTARGET_DB_PASSWORD=test-password\n",
        encoding="utf-8",
    )

    load_env_file(env_file)

    assert os.environ["SOURCE_DB_USER"] == "test-user"
    assert os.environ["TARGET_DB_PASSWORD"] == "test-password"


def test_validate_etl_config_rejects_unknown_transformations():
    config = {
        "extract": {
            "database_hostname": "source-db",
            "database_name": "source",
            "database_port": "3306",
            "sql_file": "query.sql",
        },
        "mapping": {},
        "defaults": {},
        "transformations": [{"function": "does_not_exist", "params": {}}],
        "load": {
            "database_hostname": "target-db",
            "database_name": "target",
            "database_port": "3306",
            "database_table": "table_name",
        },
    }

    with pytest.raises(ValueError, match="unknown transformations"):
        validate_etl_config(config)


def test_load_config_file_normalizes_legacy_output_path(tmp_path):
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
extract:
  database_hostname: source-db
  database_name: source
  database_port: "3306"
  sql_file: query.sql
mapping: {}
defaults: {}
transformations: []
load:
  database_hostname: target-db
  database_name: target
  database_port: "3306"
  database_table: table_name
  targeFilePath: data/output.csv
""".strip(),
        encoding="utf-8",
    )

    config = load_config_file(config_path)

    assert config["load"]["targetFilePath"] == "data/output.csv"
    assert "targeFilePath" not in config["load"]
