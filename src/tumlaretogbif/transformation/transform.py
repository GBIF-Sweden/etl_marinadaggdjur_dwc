import json
import logging

import pandas as pd

TRANSFORMATION_REGISTRY = {}
CONFIG_AWARE_TRANSFORMATIONS = {
    "add_dynamicProperties",
    "vernacular_to_scientificName",
    "drop_unmapped_columns",
}
TRANSFORMATION_REQUIRED_COLUMNS = {
    "add_individualcount": {"quantity_min"},
    "add_vitality": {"animal_condition"},
    "addprefix_associatedmedia": {"associatedMedia"},
    "format_eventTime": {"eventTime"},
    "generate_occ_id_triplet": {"institutionCode", "collectionCode", "catalogNumber"},
    "vernacular_to_scientificName": {"vernacularName"},
}


def register_transformation(func):
    TRANSFORMATION_REGISTRY[func.__name__] = func
    return func


def get_registered_transformations():
    return TRANSFORMATION_REGISTRY.copy()


def validate_transformation_requirements(df, func_name, config):
    required_columns = set(TRANSFORMATION_REQUIRED_COLUMNS.get(func_name, set()))
    if func_name == "add_dynamicProperties":
        required_columns.update(config.get("columns_to_dynamicproperties", []))

    missing_columns = sorted(column for column in required_columns if column not in df.columns)
    if missing_columns:
        raise ValueError(
            f"Transformation {func_name} requires missing columns: {', '.join(missing_columns)}"
        )


@register_transformation
def clean_whitespace(df):
    """
    Clean unwanted whitespaces, tabs, and carriage returns from all string columns in the DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: Cleaned DataFrame.
    """
    try:
        # Apply whitespace cleaning to each column
        df_cleaned = df.map(
            lambda x: (
                " ".join(str(x).split()).replace("\t", "").replace("\r", "")
                if isinstance(x, str)
                else x
            )
        )
        logging.info("Whitespace cleaning transformation completed successfully.")
        return df_cleaned

    except Exception as e:
        logging.exception(f"An error occurred during clean_whitespace: {e}")
        raise


@register_transformation
def drop_columns(df, columns_to_drop):
    """
    Drops specified columns from the DataFrame if they exist.

    Args:
        df (pd.DataFrame): Input DataFrame.
        columns_to_drop (str or list): Column name or list of column names to drop.

    Returns:
        pd.DataFrame: DataFrame after dropping specified columns.
    """
    try:
        # Convert single column name (string) to a list
        if isinstance(columns_to_drop, str):
            columns_to_drop = [columns_to_drop]

        # Only drop columns that exist in the DataFrame
        columns_to_drop = [col for col in columns_to_drop if col in df.columns]
        df.drop(columns=columns_to_drop, inplace=True)
        return df
    except KeyError as e:
        logging.error(f"Error: One or more unmapped columns not found in DataFrame: {e}")
        raise
    except Exception as e:
        logging.exception(f"An unexpected error occurred in drop_unmapped_columns: {e}")
        raise


@register_transformation
def drop_unmapped_columns(df, config):
    """
    Drop specified columns from the DataFrame based on the configuration.

    Args:
        df (pd.DataFrame): Input DataFrame.
        config (dict): Configuration dictionary.

    Returns:
        pd.DataFrame: DataFrame after dropping specified columns.
    """
    unmapped_columns = config.get('unmapped', [])
    try:
        drop_columns(df, unmapped_columns)
        logging.info("drop_unmapped_columns transformation completed successfully.")
        return df
    except Exception as e:
        logging.exception("An error occurred while dropping unmapped columns: %s", e)
        raise


@register_transformation
def add_vitality(df):
    """
    Adds a 'vitality' column to the DataFrame based on 'animal_condition' values.

    Parameters:
    df (pd.DataFrame): The DataFrame containing an 'animal_condition' column.

    Returns:
    pd.DataFrame: Modified DataFrame with an additional 'vitality' column.
    """
    # Map 'animal_condition' values to 'vitality' status: 'alive' for 'living', 'dead' for 'dead',
    # and None for any other condition.
    df['vitality'] = df['animal_condition'].apply(
        lambda x: 'alive' if x == 'living' else ('dead' if x == 'dead' else None)
    )
    logging.info("DwC term vitality added to dataframe successfully.")
    return df


def create_dynamic_properties(row, columns):
    """
    Creates a dictionary of dynamic properties from non-null and non-empty values in specified columns.

    Parameters:
    row (pd.Series): A row from the DataFrame.
    columns (list of str): List of column names to include as dynamic properties.

    Returns:
    """
    properties = {
        column: row[column]
        for column in columns
        if column in row and pd.notna(row[column]) and row[column] != ""
    }
    return properties if properties else None


@register_transformation
def add_dynamicProperties(df, config):
    """
    Adds a 'dynamicProperties' column to the DataFrame based on configuration-specified columns.

    Parameters:
    df (pd.DataFrame): The DataFrame to transform.
    config (dict): Configuration dictionary.

    Returns:
    pd.DataFrame: DataFrame with dynamicProperties column.
    """
    columns = config.get("columns_to_dynamicproperties", [])
    df["dynamicProperties"] = df.apply(
        lambda row: json.dumps(create_dynamic_properties(row, columns), ensure_ascii=False)
        if create_dynamic_properties(row, columns)
        else None,
        axis=1,
    )
    logging.info("dynamicProperties column added to dataframe successfully.")
    return df


@register_transformation
def addprefix_associatedmedia(df, url):
    """
    Adds a URL prefix to the associatedMedia values.

    Args:
        df (pd.DataFrame): Input DataFrame.
        url (str): Prefix URL to prepend.

    Returns:
        pd.DataFrame: DataFrame with prefixed associatedMedia values.
    """
    if "associatedMedia" not in df.columns:
        logging.warning("associatedMedia column not found in DataFrame.")
        return df

    def prefix_media(value):
        if pd.isna(value) or value == "":
            return value
        return " | ".join(
            [f"{url}{item.strip()}" for item in str(value).split(",") if item.strip()]
        )

    df["associatedMedia"] = df["associatedMedia"].apply(prefix_media)
    logging.info("associatedMedia URL prefix added successfully.")
    return df


@register_transformation
def generate_occ_id_triplet(df):
    """
    Generates an occurrenceID based on institutionCode, collectionCode, and catalogNumber.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: DataFrame with occurrenceID column.
    """
    if not {"institutionCode", "collectionCode", "catalogNumber"}.issubset(df.columns):
        raise ValueError(
            "Missing required columns for generate_occ_id_triplet: institutionCode, collectionCode, catalogNumber"
        )

    df["occurrenceID"] = (
        df["institutionCode"].astype(str)
        + ":"
        + df["collectionCode"].astype(str)
        + ":"
        + df["catalogNumber"].astype(str)
    )
    cols = list(df.columns)
    if "occurrenceID" in cols:
        cols.insert(0, cols.pop(cols.index("occurrenceID")))
        df = df[cols]
    return df


def format_time(row):
    """
    Formats a timedelta or time-like value into HH:MM:SS.

    Args:
        row (pd.Series): A row from the DataFrame.

    Returns:
        str or None: Formatted time string or None.
    """
    if pd.isna(row):
        return None

    try:
        return str(row)
    except Exception:
        return None


@register_transformation
def format_eventTime(df):
    """
    Formats eventTime values in the DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: DataFrame with formatted eventTime.
    """
    if "eventTime" not in df.columns:
        logging.warning("eventTime column not found in DataFrame.")
        return df

    df["eventTime"] = df["eventTime"].apply(format_time)
    logging.info("eventTime formatting completed successfully.")
    return df


@register_transformation
def add_individualcount(df):
    """
    Adds or preserves individualCount in the DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: DataFrame with individualCount present.
    """
    if "individualCount" not in df.columns:
        df["individualCount"] = 1
        logging.info("individualCount added with default value 1.")
    else:
        df["individualCount"] = df["individualCount"].fillna(1).astype(int)
        logging.info("individualCount normalized successfully.")
    return df


@register_transformation
def convert_column_to_int(df, column_name):
    """
    Converts a specified DataFrame column to integer type.

    Args:
        df (pd.DataFrame): Input DataFrame.
        column_name (str): Column to convert.

    Returns:
        pd.DataFrame: DataFrame with converted column.
    """
    if column_name not in df.columns:
        raise ValueError(f"Column '{column_name}' not found in DataFrame.")

    df[column_name] = pd.to_numeric(df[column_name], errors="coerce").fillna(0).astype(int)
    logging.info("%s converted to int successfully.", column_name)
    return df


@register_transformation
def vernacular_to_scientificName(df, lookup_table):
    """
    Maps vernacular names to scientific names using a lookup table.

    Args:
        df (pd.DataFrame): Input DataFrame.
        lookup_table (dict): Mapping from vernacular to scientific names.

    Returns:
        pd.DataFrame: DataFrame with scientificName column.
    """
    if "vernacularName" not in df.columns:
        raise ValueError("vernacularName column not found in DataFrame.")

    df["scientificName"] = df["vernacularName"].map(lookup_table).fillna(df.get("scientificName", pd.NA))
    logging.info("Mapped vernacular names to scientific names successfully.")
    return df
