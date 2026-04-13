import logging

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


# Function to create a database connection using the credentials
def create_connection(db_credentials, db_config):
    try:
        engine = create_engine(
            URL.create(
                "mysql+pymysql",
                username=db_credentials["database_user"],
                password=db_credentials["database_password"],
                host=db_config["database_hostname"],
                port=int(db_config["database_port"]),
                database=db_config["database_name"],
                query={"charset": db_config["charset"]},
            )
        )
        return engine
    except Exception as e:
        logging.error(f"An error occurred while connecting to the database: {e}")
        raise


# Function to execute a SELECT query and yield data in chunks
def fetch_data_in_chunks(engine, query, batch_size, dtypes_dict):
    try:
        with engine.connect() as connection:
            for chunk in pd.read_sql_query(
                query, connection, chunksize=batch_size, dtype=dtypes_dict
            ):
                chunk = chunk.astype(dtypes_dict)
                # Filter out empty or all-NA chunks
                if not chunk.empty and not chunk.isna().all().all():
                    yield chunk
    except Exception as e:
        logging.error(f"An error occurred while fetching data: {e}")
        raise
