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
