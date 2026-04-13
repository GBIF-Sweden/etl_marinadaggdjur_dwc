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
