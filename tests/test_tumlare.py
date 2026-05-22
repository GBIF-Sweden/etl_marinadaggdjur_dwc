import json

import pandas as pd
import yaml
from sqlalchemy.engine import URL

from marinadaggdjur import etl_runner
from marinadaggdjur.extraction.extract import create_connection
from marinadaggdjur.loading.load import execute_batch_with_retry
from marinadaggdjur.transformation.transform import apply_transformations


def test_tumlare_transformation_smoke_path():
    df = pd.DataFrame(
        [
            {
                "id": 7,
                "observation_date": "2024-01-01",
                "animal_condition": "living",
                "time_start": "01:02:03",
                "time_end": "02:00:00",
                "latitude": "59.0",
                "longitude": "18.0",
                "distance_min": 10,
                "distance_max": 12,
                "quantity_min": 3,
                "quantity_max": 4,
                "quantity_cubs_min": 1,
                "quantity_cubs_max": 1,
                "quantity_dead": 0,
                "dead_length_min": None,
                "dead_length_max": None,
                "observer_comment": "  hello\tworld\r ",
                "updated_at": "2024-01-02",
                "name": "Stockholm",
                "animal_decomposion": None,
                "associatedMedia": "one.jpg,two.jpg",
            }
        ]
    )
    config = {
        "mapping": {
            "id": "catalogNumber",
            "observation_date": "eventDate",
            "time_start": "eventTime",
            "latitude": "decimalLatitude",
            "longitude": "decimalLongitude",
            "observer_comment": "occurrenceRemarks",
            "updated_at": "modified",
            "name": "county",
            "vitality": "vitality",
        },
        "defaults": {
            "institutionCode": "NRM",
            "collectionCode": "Porpoises",
        },
        "columns_to_dynamicproperties": [
            "distance_min",
            "distance_max",
            "quantity_min",
            "quantity_max",
            "quantity_cubs_min",
            "quantity_cubs_max",
            "quantity_dead",
            "dead_length_min",
            "dead_length_max",
        ],
        "unmapped": [
            "animal_condition",
            "time_end",
            "distance_min",
            "distance_max",
            "quantity_min",
            "quantity_max",
            "quantity_cubs_min",
            "quantity_cubs_max",
            "quantity_dead",
            "dead_length_min",
            "dead_length_max",
            "animal_decomposion",
        ],
        "transformations": [
            {"function": "clean_whitespace", "params": {}},
            {
                "function": "addprefix_associatedmedia",
                "params": {"url": "https://example.invalid/images/"},
            },
            {"function": "generate_occ_id_triplet", "params": {}},
            {"function": "add_vitality", "params": {}},
            {"function": "add_dynamicProperties", "params": {}},
            {"function": "format_eventTime", "params": {}},
            {"function": "add_individualcount", "params": {}},
            {"function": "convert_column_to_int", "params": {"columnname": "individualCount"}},
            {"function": "drop_unmapped_columns", "params": {}},
        ],
    }

    transformed = apply_transformations(df, config)

    assert transformed.loc[0, "occurrenceID"] == "NRM:Porpoises:7"
    assert transformed.loc[0, "eventTime"] == "01:02:03"
    assert transformed.loc[0, "vitality"] == "alive"
    assert transformed.loc[0, "associatedMedia"] == (
        "https://example.invalid/images/one.jpg | https://example.invalid/images/two.jpg"
    )
    assert transformed.loc[0, "individualCount"] == 3
    assert json.loads(transformed.loc[0, "dynamicProperties"])["distance_min"] == 10
    assert "animal_condition" not in transformed.columns


def test_run_etl_processes_chunks_incrementally(tmp_path, monkeypatch):
    sql_path = tmp_path / "query.sql"
    sql_path.write_text("select 1", encoding="utf-8")
    output_path = tmp_path / "output.csv"
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "extract": {
                    "database_hostname": "example",
                    "database_name": "source",
                    "database_port": "3306",
                    "charset": "utf8mb4",
                    "batch_size": 2,
                    "sql_file": str(sql_path),
                },
                "dtype_dict": {},
                "mapping": {},
                "defaults": {},
                "transformations": [],
                "load": {
                    "database_hostname": "example",
                    "database_name": "target",
                    "database_port": "3306",
                    "database_table": "table_name",
                    "database_table_pk_column": "id",
                    "targetFilePath": str(output_path),
                    "write_to_file": True,
                    "write_to_db": True,
                    "batch_size": 10,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SOURCE_DB_USER", "source-user")
    monkeypatch.setenv("SOURCE_DB_PASSWORD", "source-password")
    monkeypatch.setenv("TARGET_DB_USER", "target-user")
    monkeypatch.setenv("TARGET_DB_PASSWORD", "target-password")

    chunks = [
        pd.DataFrame([{"id": 1, "value": "a"}]),
        pd.DataFrame([{"id": 2, "value": "b"}]),
    ]
    upsert_calls = []

    class DummyEngine:
        def dispose(self):
            return None

    monkeypatch.setattr(
        etl_runner, "create_connection", lambda *_args, **_kwargs: DummyEngine()
    )
    monkeypatch.setattr(
        etl_runner, "fetch_data_in_chunks", lambda *_args, **_kwargs: iter(chunks)
    )
    monkeypatch.setattr(
        etl_runner,
        "apply_transformations",
        lambda df, _config: df.assign(processed=True),
    )
    monkeypatch.setattr(
        etl_runner,
        "upsert_dataframe_in_batches",
        lambda df, *_args, **_kwargs: upsert_calls.append(df.copy()),
    )

    exit_code = etl_runner.run_etl(str(config_path))

    assert exit_code == 0
    assert len(upsert_calls) == 2
    assert output_path.exists()
    written = pd.read_csv(output_path)
    assert written.shape[0] == 2
    assert list(written["id"]) == [1, 2]
    assert written["processed"].tolist() == [True, True]


def test_execute_batch_with_retry_retries_and_commits():
    events = []

    class DummySession:
        def __init__(self):
            self.attempts = 0

        def execute(self, _stmt):
            self.attempts += 1
            events.append(f"execute-{self.attempts}")
            if self.attempts == 1:
                raise RuntimeError("temporary failure")

        def commit(self):
            events.append("commit")

        def rollback(self):
            events.append("rollback")

    session = DummySession()

    execute_batch_with_retry(
        session,
        stmt=object(),
        batch_number=1,
        max_retries=2,
        retry_delay_seconds=0,
    )

    assert events == ["execute-1", "rollback", "execute-2", "commit"]


def test_run_etl_resolves_sql_path_relative_to_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    sql_dir = config_dir / "sql"
    sql_dir.mkdir()
    sql_path = sql_dir / "query.sql"
    sql_path.write_text("select 1", encoding="utf-8")
    output_path = tmp_path / "output.csv"
    config_path = config_dir / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "extract": {
                    "database_hostname": "example",
                    "database_name": "source",
                    "database_port": "3306",
                    "charset": "utf8mb4",
                    "batch_size": 1,
                    "sql_file": "sql/query.sql",
                },
                "dtype_dict": {},
                "mapping": {},
                "defaults": {},
                "transformations": [],
                "load": {
                    "database_hostname": "example",
                    "database_name": "target",
                    "database_port": "3306",
                    "database_table": "table_name",
                    "database_table_pk_column": "id",
                    "targetFilePath": str(output_path),
                    "write_to_file": False,
                    "write_to_db": False,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SOURCE_DB_USER", "source-user")
    monkeypatch.setenv("SOURCE_DB_PASSWORD", "source-password")
    monkeypatch.setenv("TARGET_DB_USER", "target-user")
    monkeypatch.setenv("TARGET_DB_PASSWORD", "target-password")

    class DummyEngine:
        def dispose(self):
            return None

    captured = {}
    monkeypatch.setattr(
        etl_runner, "create_connection", lambda *_args, **_kwargs: DummyEngine()
    )

    def fake_fetch(_engine, query, *_args, **_kwargs):
        captured["query"] = query
        return iter([pd.DataFrame([{"id": 1}])])

    monkeypatch.setattr(etl_runner, "fetch_data_in_chunks", fake_fetch)
    monkeypatch.setattr(etl_runner, "apply_transformations", lambda df, _config: df)

    exit_code = etl_runner.run_etl(str(config_path))

    assert exit_code == 0
    assert captured["query"] == "select 1"


def test_apply_transformations_fails_on_unknown_function():
    df = pd.DataFrame([{"id": 1}])
    config = {
        "mapping": {},
        "defaults": {},
        "transformations": [{"function": "does_not_exist", "params": {}}],
    }

    try:
        apply_transformations(df, config)
    except ValueError as exc:
        assert "Unknown transformation function" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown transformation.")


def test_create_connection_uses_sqlalchemy_url(monkeypatch):
    captured = {}

    def fake_create_engine(url):
        captured["url"] = url
        return object()

    monkeypatch.setattr("marinadaggdjur.extraction.extract.create_engine", fake_create_engine)

    create_connection(
        {"database_user": "user", "database_password": "p@ss:word"},
        {
            "database_hostname": "db.example.org",
            "database_port": "3306",
            "database_name": "source_db",
            "charset": "utf8mb4",
        },
    )

    assert isinstance(captured["url"], URL)
    assert captured["url"].password == "p@ss:word"


def test_apply_transformations_validates_required_columns():
    df = pd.DataFrame([{"catalogNumber": "1"}])
    config = {
        "mapping": {},
        "defaults": {
            "institutionCode": "NRM",
            "collectionCode": "Porpoises",
        },
        "transformations": [{"function": "add_individualcount", "params": {}}],
    }

    try:
        apply_transformations(df, config)
    except ValueError as exc:
        assert "requires missing columns" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing transformation columns.")


def test_run_etl_logs_structured_summary(tmp_path, monkeypatch, caplog):
    sql_path = tmp_path / "query.sql"
    sql_path.write_text("select 1", encoding="utf-8")
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "extract": {
                    "database_hostname": "example",
                    "database_name": "source",
                    "database_port": "3306",
                    "charset": "utf8mb4",
                    "batch_size": 1,
                    "sql_file": str(sql_path),
                },
                "dtype_dict": {},
                "mapping": {},
                "defaults": {},
                "transformations": [],
                "load": {
                    "database_hostname": "example",
                    "database_name": "target",
                    "database_port": "3306",
                    "database_table": "table_name",
                    "database_table_pk_column": "id",
                    "write_to_file": False,
                    "write_to_db": False,
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SOURCE_DB_USER", "source-user")
    monkeypatch.setenv("SOURCE_DB_PASSWORD", "source-password")
    monkeypatch.setenv("TARGET_DB_USER", "target-user")
    monkeypatch.setenv("TARGET_DB_PASSWORD", "target-password")

    class DummyEngine:
        def dispose(self):
            return None

    monkeypatch.setattr(
        etl_runner, "create_connection", lambda *_args, **_kwargs: DummyEngine()
    )
    monkeypatch.setattr(
        etl_runner,
        "fetch_data_in_chunks",
        lambda *_args, **_kwargs: iter([pd.DataFrame([{"id": 1}])]),
    )
    monkeypatch.setattr(etl_runner, "apply_transformations", lambda df, _config: df)

    with caplog.at_level("INFO"):
        exit_code = etl_runner.run_etl(str(config_path))

    assert exit_code == 0
    assert any("ETL_RUN_SUMMARY" in record.message for record in caplog.records)
