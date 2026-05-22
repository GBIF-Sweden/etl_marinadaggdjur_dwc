from pathlib import Path

from marinadaggdjur.config.config_loader import load_config_file, validate_etl_config


def main():
    config_dir = Path("etl_configs")
    etl_configs = sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in config_dir.glob(pattern)
    )

    for config_path in etl_configs:
        config = load_config_file(config_path)
        validate_etl_config(config)
        sql_path = Path(config["extract"]["sql_file"])
        if not sql_path.is_absolute():
            sql_path = config_path.parent / sql_path

        if not sql_path.exists():
            raise FileNotFoundError(f"SQL file not found for {config_path}: {sql_path}")

    print(f"Validated {len(etl_configs)} ETL configs.")


if __name__ == "__main__":
    main()
