import argparse
import sys

from tumlaretogbif.etl_runner import run_etl
from tumlaretogbif.utils.logging_utils import configure_logging

# Configure logging
configure_logging()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="ETL process from database using configuration files."
    )
    parser.add_argument("config_path", type=str, help="Path to the configuration file.")
    parser.add_argument(
        "legacy_source_db_credentials_path",
        nargs="?",
        default=None,
        help="Deprecated positional path to the source database credentials JSON file.",
    )
    parser.add_argument(
        "legacy_target_db_credentials_path",
        nargs="?",
        default=None,
        help="Deprecated positional path to the target database credentials JSON file.",
    )
    parser.add_argument(
        "--source-db-credentials-path",
        dest="source_db_credentials_path",
        type=str,
        default=None,
        help="Optional path to the source database credentials JSON file.",
    )
    parser.add_argument(
        "--target-db-credentials-path",
        dest="target_db_credentials_path",
        type=str,
        default=None,
        help="Optional path to the target database credentials JSON file.",
    )
    parser.add_argument(
        "--env-file",
        dest="env_file_path",
        type=str,
        default=None,
        help="Optional path to a .env file containing SOURCE_DB_* and TARGET_DB_* values.",
    )
    args = parser.parse_args(argv)
    source_db_credentials_path = (
        args.source_db_credentials_path or args.legacy_source_db_credentials_path
    )
    target_db_credentials_path = (
        args.target_db_credentials_path or args.legacy_target_db_credentials_path
    )
    return run_etl(
        args.config_path,
        source_db_credentials_path,
        target_db_credentials_path,
        args.env_file_path,
    )


if __name__ == "__main__":
    sys.exit(main())
