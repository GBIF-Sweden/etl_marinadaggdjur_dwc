import logging
import random
import time

from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker


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
        table = Table(load_config['database_table'], metadata, autoload_with=engine)
        table_columns = set(table.columns.keys())
        dropped_columns = [col for col in df.columns if col not in table_columns]
        if dropped_columns:
            raise ValueError(
                "Refusing to drop columns missing from target table "
                f"{load_config['database_table']}: {', '.join(dropped_columns)}"
            )
        pk = load_config["database_table_pk_column"]
        if pk not in df.columns:
            raise ValueError(
                f"Primary key column '{pk}' is missing from the DataFrame for {load_config['database_table']}."
            )
        # Insert/Update in batches
        Session = sessionmaker(bind=engine)

        with Session() as session:
            for batch_number, start in enumerate(range(0, len(df), batch_size), start=1):
                batch_df = df.iloc[start:start + batch_size]
                stmt = insert(table).values(batch_df.to_dict(orient='records'))
                update_columns = {col: stmt.inserted[col] for col in df.columns if col != pk}
                stmt = stmt.on_duplicate_key_update(**update_columns)
                execute_batch_with_retry(
                    session,
                    stmt,
                    batch_number,
                    max_retries,
                    retry_delay_seconds,
                )

        logging.info("Database insert/update completed successfully.")
    except Exception as e:
        logging.error(f"Error during database insert/update: {e}")
        raise
    finally:
        if engine is not None:
            engine.dispose()
