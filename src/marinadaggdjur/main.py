import argparse
import sys

from marinadaggdjur.etl_runner import run_etl
from marinadaggdjur.utils.logging_utils import configure_logging

# Configure logging
configure_logging()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="ETL process from database using configuration files."
    )
    parser.add_argument("config_path", type=str, help="Path to the configuration file.")
    parser.add_argument(
        "--env-file",
        dest="env_file_path",
        type=str,
        default=None,
        help="Optional path to a .env file containing SOURCE_DB_* and TARGET_DB_* values.",
    )
    args = parser.parse_args(argv)
    return run_etl(
        args.config_path,
        args.env_file_path,
    )


if __name__ == "__main__":
    sys.exit(main())
