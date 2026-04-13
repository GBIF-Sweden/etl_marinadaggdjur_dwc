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
