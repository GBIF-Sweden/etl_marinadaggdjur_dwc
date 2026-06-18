import logging
import math
import random
import time
from datetime import date, datetime, time as datetime_time, timezone
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, Float, Integer, JSON, Numeric, String, Time


def _is_missing_value(value):
    if value is None:
        return True

    if isinstance(value, (list, tuple, dict, set)):
        return False

    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False

    if missing is pd.NA:
        return True
    if isinstance(missing, (bool, np.bool_)):
        return bool(missing)
    return False


def _format_bad_value(value):
    text = repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


def _normalize_datetime(value):
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    elif isinstance(value, np.datetime64):
        value = pd.Timestamp(value).to_pydatetime()
    elif isinstance(value, str):
        value = pd.to_datetime(value, errors="raise").to_pydatetime()

    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return value


def _normalize_date(value):
    value = _normalize_datetime(value)
    if isinstance(value, datetime):
        return value.date()
    return value


def _normalize_time(value):
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    elif isinstance(value, np.datetime64):
        value = pd.Timestamp(value).to_pydatetime()
    elif isinstance(value, str):
        value = (datetime(1970, 1, 1) + pd.to_timedelta(value, errors="raise")).time()
        return value
    elif isinstance(value, pd.Timedelta):
        value = (datetime(1970, 1, 1) + value).time()
        return value

    if isinstance(value, datetime) and value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, datetime_time):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    return value


def _normalize_bool(value, column_name):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "1", "yes", "y"}:
            return True
        if normalized in {"false", "f", "0", "no", "n"}:
            return False
    raise ValueError(f"Column '{column_name}' contains a value that cannot be coerced to boolean: {_format_bad_value(value)}")


def _normalize_integer(value, column_name):
    if isinstance(value, bool):
        raise ValueError(
            f"Column '{column_name}' contains a boolean value where an integer is required: {_format_bad_value(value)}"
        )
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(value):
            raise ValueError(
                f"Column '{column_name}' contains a non-finite float: {_format_bad_value(value)}"
            )
        if not value.is_integer():
            raise ValueError(
                f"Column '{column_name}' contains a non-integer float: {_format_bad_value(value)}"
            )
        return int(value)
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise ValueError(
                f"Column '{column_name}' contains a non-integer decimal: {_format_bad_value(value)}"
            )
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise ValueError(
        f"Column '{column_name}' contains a value that cannot be coerced to integer: {_format_bad_value(value)}"
    )


def _normalize_float(value, column_name):
    if isinstance(value, bool):
        raise ValueError(
            f"Column '{column_name}' contains a boolean value where a float is required: {_format_bad_value(value)}"
        )
    if isinstance(value, (int, float, np.integer, np.floating, Decimal)):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(
                f"Column '{column_name}' contains a non-finite float: {_format_bad_value(value)}"
            )
        return value
    if isinstance(value, str):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(
                f"Column '{column_name}' contains a non-finite float: {_format_bad_value(value)}"
            )
        return value
    raise ValueError(
        f"Column '{column_name}' contains a value that cannot be coerced to float: {_format_bad_value(value)}"
    )


def _normalize_numeric(value, column_name):
    if isinstance(value, bool):
        raise ValueError(
            f"Column '{column_name}' contains a boolean value where a numeric value is required: {_format_bad_value(value)}"
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, np.integer)):
        return Decimal(int(value))
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(value):
            raise ValueError(
                f"Column '{column_name}' contains a non-finite numeric value: {_format_bad_value(value)}"
            )
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    raise ValueError(
        f"Column '{column_name}' contains a value that cannot be coerced to Decimal: {_format_bad_value(value)}"
    )


def _normalize_string(value, column_name):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, datetime_time):
        return value.isoformat()
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(
            f"Column '{column_name}' contains a complex value that cannot be stored as text: {_format_bad_value(value)}"
        )
    return value


def _coerce_mysql_value(value, column):
    if _is_missing_value(value):
        return None

    if isinstance(value, np.generic):
        value = value.item()

    column_type = column.type
    column_name = column.name

    if isinstance(column_type, JSON):
        return value
    if isinstance(column_type, Boolean):
        return _normalize_bool(value, column_name)
    if isinstance(column_type, Integer):
        return _normalize_integer(value, column_name)
    if isinstance(column_type, Float):
        return _normalize_float(value, column_name)
    if isinstance(column_type, Numeric):
        return _normalize_numeric(value, column_name)
    if isinstance(column_type, DateTime):
        return _normalize_datetime(value)
    if isinstance(column_type, Date):
        return _normalize_date(value)
    if isinstance(column_type, Time):
        return _normalize_time(value)
    if isinstance(column_type, String):
        return _normalize_string(value, column_name)

    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(
            f"Column '{column_name}' contains a complex value that is not supported by MySQL loading: {_format_bad_value(value)}"
        )
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        raise ValueError(
            f"Column '{column_name}' contains a non-finite float: {_format_bad_value(value)}"
        )
    return value


def _batch_records_for_mysql(batch_df):
    """
    Backward-compatible helper for raw dataframe serialization.

    This only normalizes pandas missing values and is retained for callers that still rely on the
    previous behavior.
    """
    return (
        batch_df.copy()
        .astype(object)
        .where(pd.notna(batch_df), None)
        .to_dict(orient="records")
    )


def _validate_primary_key(df, pk_column, table_name):
    if pk_column not in df.columns:
        raise ValueError(
            f"Primary key column '{pk_column}' is missing from the DataFrame for {table_name}."
        )

    missing_mask = df[pk_column].map(_is_missing_value)
    if missing_mask.any():
        bad_rows = df.index[missing_mask].tolist()
        sample_rows = ", ".join(str(row) for row in bad_rows[:5])
        raise ValueError(
            f"Primary key column '{pk_column}' contains missing values for {table_name}. "
            f"Problem rows: {sample_rows}"
        )

    try:
        duplicate_mask = df[pk_column].duplicated(keep=False)
    except TypeError as exc:
        raise ValueError(
            f"Primary key column '{pk_column}' contains unhashable values in {table_name}."
        ) from exc

    if duplicate_mask.any():
        duplicate_values = df.loc[duplicate_mask, pk_column].drop_duplicates().tolist()
        sample_values = ", ".join(_format_bad_value(value) for value in duplicate_values[:5])
        raise ValueError(
            f"Primary key column '{pk_column}' contains duplicate values for {table_name}. "
            f"Problem values: {sample_values}"
        )


def _prepare_batch_records_for_mysql(table, batch_df):
    """
    Convert a batch dataframe to MySQL-safe record dicts.

    The loader reflects the target schema and coerces each column to a SQLAlchemy/MySQL friendly
    Python scalar before binding parameters.
    """
    table_columns = {column.name: column for column in table.columns}
    records = []

    for row_index, row in batch_df.iterrows():
        record = {}
        for column_name in batch_df.columns:
            column = table_columns[column_name]
            try:
                record[column_name] = _coerce_mysql_value(row[column_name], column)
            except Exception as exc:
                raise ValueError(
                    f"Failed to normalize row {row_index} column '{column_name}' for table '{table.name}': {exc}"
                ) from exc
        records.append(record)

    return records


def execute_batch_with_retry(session, stmt, batch_number, max_retries, retry_delay_seconds):
    for attempt in range(1, max_retries + 1):
        try:
            session.execute(stmt)
            session.commit()
            if attempt > 1:
                logging.info(
                    "Batch %s succeeded on retry attempt %s.",
                    batch_number,
                    attempt,
                )
            return
        except Exception:
            session.rollback()
            if attempt == max_retries:
                raise
            delay_seconds = min(
                retry_delay_seconds * (2 ** (attempt - 1)),
                retry_delay_seconds * (2 ** (max_retries - 1)),
            )
            delay_seconds += random.uniform(0, max(delay_seconds * 0.2, 0.0))
            logging.warning(
                "Batch %s failed on attempt %s/%s. Retrying in %.2fs.",
                batch_number,
                attempt,
                max_retries,
                delay_seconds,
            )
            time.sleep(delay_seconds)


def upsert_dataframe_in_batches(df, load_config, db_config, batch_size=1000):
    """
    Inserts or Updates a DataFrame into a MySQL table in batches using SQLAlchemy 2.0.

    Parameters:
    df (pd.DataFrame): The DataFrame to be inserted/updated.
    load_config (dict): Configuration for the database load.
    db_config (dict): Configuration for the database connection.
    batch_size (int): Number of rows per batch for the upsert operation.

    Returns:
    None
    """
    logging.info("Database insert/update process starting...")
    engine = None
    if batch_size <= 0:
        raise ValueError("batch_size must be a positive integer.")
    max_retries = int(load_config.get("max_retries", 3))
    retry_delay_seconds = int(load_config.get("retry_delay_seconds", 2))
    try:
        engine = create_engine(
            URL.create(
                "mysql+pymysql",
                username=db_config["database_user"],
                password=db_config["database_password"],
                host=load_config["database_hostname"],
                port=int(load_config["database_port"]),
                database=load_config["database_name"],
                query={"charset": "utf8mb4"},
            )
        )
        metadata = MetaData()
        table = Table(load_config["database_table"], metadata, autoload_with=engine)
        table_columns = {column.name for column in table.columns}
        dropped_columns = [col for col in df.columns if col not in table_columns]
        if dropped_columns:
            raise ValueError(
                "Refusing to drop columns missing from target table "
                f"{load_config['database_table']}: {', '.join(dropped_columns)}"
            )
        pk = load_config["database_table_pk_column"]
        if pk not in table_columns:
            raise ValueError(
                f"Primary key column '{pk}' does not exist in target table '{load_config['database_table']}'."
            )
        _validate_primary_key(df, pk, load_config["database_table"])
        if df.empty:
            logging.info("DataFrame is empty; skipping database insert/update.")
            return

        # Insert/Update in batches
        Session = sessionmaker(bind=engine)

        with Session() as session:
            for batch_number, start in enumerate(range(0, len(df), batch_size), start=1):
                batch_df = df.iloc[start:start + batch_size]
                records = _prepare_batch_records_for_mysql(table, batch_df)
                if not records:
                    continue
                stmt = insert(table).values(records)
                update_columns = {
                    column.name: stmt.inserted[column.name]
                    for column in table.columns
                    if column.name != pk
                }
                stmt = stmt.on_duplicate_key_update(**update_columns)
                execute_batch_with_retry(
                    session,
                    stmt,
                    batch_number,
                    max_retries,
                    retry_delay_seconds,
                )

        logging.info("Database insert/update completed successfully.")
    except Exception:
        logging.exception("Error during database insert/update")
        raise
    finally:
        if engine is not None:
            engine.dispose()
