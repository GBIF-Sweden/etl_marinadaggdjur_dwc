import json
import logging
import os
import time
import uuid
from pathlib import Path

from marinadaggdjur.config.config_loader import (
    load_config_file,
    load_db_credentials,
    load_env_file,
    validate_etl_config,
)
from marinadaggdjur.extraction.extract import create_connection, fetch_data_in_chunks
from marinadaggdjur.loading.load import upsert_dataframe_in_batches
from marinadaggdjur.transformation.transform import apply_transformations


def write_dataframe_to_csv(df, load_config, file_written):
    processed_file_path = load_config.get("targetFilePath", "output.csv")
    Path(processed_file_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        processed_file_path,
        sep=load_config.get("delimiter", ","),
        encoding=load_config.get("encoding", "utf-8"),
        index=False,
        mode="a" if file_written else "w",
        header=not file_written,
    )
    logging.info("Wrote output file chunk: path=%s rows=%s", processed_file_path, len(df))
    return True


def resolve_sql_file_path(config_file_path, extract_config):
    sql_file_path = Path(extract_config["sql_file"])
    if not sql_file_path.is_absolute():
        sql_file_path = config_file_path.parent / sql_file_path
    return sql_file_path


def load_select_query(config_file_path, extract_config):
    sql_file_path = resolve_sql_file_path(config_file_path, extract_config)
    with sql_file_path.open("r", encoding="utf-8") as file:
        return file.read()


def log_run_summary(summary, level=logging.INFO):
    logging.log(level, "ETL_RUN_SUMMARY %s", json.dumps(summary, sort_keys=True))


def run_etl(
    config_path,
    env_file_path=None,
):
    started_at = time.monotonic()
    config_file_path = Path(config_path).resolve()
    run_id = os.getenv("RUN_ID", str(uuid.uuid4()))
    config_name = config_file_path.name
    os.environ["RUN_ID"] = run_id
    os.environ["CONFIG_NAME"] = config_name

    summary = {
        "run_id": run_id,
        "config_name": config_name,
        "config_path": str(config_file_path),
        "status": "failed",
        "duration_seconds": 0.0,
        "chunks_processed": 0,
        "rows_processed": 0,
        "write_to_file": False,
        "write_to_db": False,
        "target_table": None,
    }

    try:
        if env_file_path:
            load_env_file(env_file_path)

        logging.info(
            "ETL run started: config_path=%s",
            str(config_file_path),
            extra={"run_id": run_id, "config_name": config_name},
        )

        config = load_config_file(config_file_path)
        validate_etl_config(config)
        source_db_credentials = load_db_credentials("SOURCE")
        target_db_credentials = load_db_credentials("TARGET")

        extract_config = config["extract"]
        select_query = load_select_query(config_file_path, extract_config)
        batch_size = extract_config.get("batch_size")
        dtypes_dict = config["dtype_dict"]
        engine = create_connection(source_db_credentials, extract_config)
        load_config = config.get("load", {})
        load_batch_size = int(load_config.get("batch_size", 100))
        file_written = False

        summary["write_to_file"] = bool(load_config.get("write_to_file"))
        summary["write_to_db"] = bool(load_config.get("write_to_db"))
        summary["target_table"] = load_config.get("database_table")

        try:
            for extracted_chunk in fetch_data_in_chunks(engine, select_query, batch_size, dtypes_dict):
                summary["chunks_processed"] += 1
                transformed_chunk = apply_transformations(extracted_chunk, config)
                summary["rows_processed"] += len(transformed_chunk)

                logging.info(
                    "Chunk processed: chunk=%s rows=%s columns=%s",
                    summary["chunks_processed"],
                    transformed_chunk.shape[0],
                    transformed_chunk.shape[1],
                    extra={"run_id": run_id, "config_name": config_name},
                )

                if load_config.get("write_to_file"):
                    file_written = write_dataframe_to_csv(transformed_chunk, load_config, file_written)

                if load_config.get("write_to_db"):
                    upsert_dataframe_in_batches(
                        transformed_chunk,
                        load_config,
                        target_db_credentials,
                        load_batch_size,
                    )
        finally:
            engine.dispose()

        if summary["chunks_processed"] == 0:
            logging.warning(
                "No data returned from extraction query.",
                extra={"run_id": run_id, "config_name": config_name},
            )

        summary["status"] = "success"
        summary["duration_seconds"] = round(time.monotonic() - started_at, 4)
        logging.info(
            "ETL process completed successfully in %.2fs: chunks=%s rows=%s",
            summary["duration_seconds"],
            summary["chunks_processed"],
            summary["rows_processed"],
            extra={"run_id": run_id, "config_name": config_name},
        )
        log_run_summary(summary)
        return 0

    except Exception as exc:
        summary["duration_seconds"] = round(time.monotonic() - started_at, 4)
        logging.exception(
            "ETL process failed after %.2fs: %s",
            summary["duration_seconds"],
            exc,
            extra={"run_id": run_id, "config_name": config_name},
        )
        log_run_summary(summary, level=logging.ERROR)
        return 1
