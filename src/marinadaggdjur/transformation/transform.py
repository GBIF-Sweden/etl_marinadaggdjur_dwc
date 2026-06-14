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
    dict or None: Dictionary of non-null, non-empty column values, or None if all values are null/empty.
    """
    # Create dictionary with non-null and non-empty values from specified columns in the row.
    properties = {col: row[col] for col in columns if pd.notnull(row[col]) and row[col] != ''}
    # Return dictionary or None if dictionary is empty.
    return properties if properties else None


@register_transformation
def add_dynamicProperties(df, config):
    """
    Adds a 'dynamicProperties' column to the DataFrame, based on specified columns in the config,
    ensuring JSON validity and character encoding for database compatibility.

    Parameters:
    df (pd.DataFrame): The DataFrame to which 'dynamicProperties' will be added.
    config (dict): Configuration dictionary containing 'columns_to_dynamicproperties',
                   which lists columns to include as dynamic properties.

    Returns:
    pd.DataFrame: DataFrame with an added 'dynamicProperties' column as JSON-encoded strings.

    Raises:
    Exception: If an error occurs during DataFrame processing.
    """
    # Extract specified columns to be included in 'dynamicProperties' from the config.
    columns_to_dynamicproperties = config['columns_to_dynamicproperties']
    # Work on a copy of the DataFrame to avoid modifying the original data.
    df = df.copy()

    try:
        # Populate 'dynamicProperties' with JSON-formatted strings.
        df['dynamicProperties'] = df.apply(
            lambda row: json.dumps(
                create_dynamic_properties(row, columns_to_dynamicproperties),
                ensure_ascii=False,
            ),
            axis=1
        )
        logging.info("DwC term dynamicProperties added to dataframe successfully as valid JSON.")
        return df
    except Exception as e:
        # Log the exception and re-raise it for further handling if necessary.
        logging.exception(f"An error occurred in add_dynamicProperties transformation: {e}")
        raise


@register_transformation
def addprefix_associatedmedia(df, url):
    """
    Prepend the specified URL to elements in the 'associatedMedia' column.

    Args:
        df (pd.DataFrame): Input DataFrame with 'associatedMedia' column.
        url (str): URL prefix to be prepended.

    Returns:
        pd.DataFrame: Updated DataFrame with modified 'associatedMedia' column.
    """

    def fix_value(value):
        if pd.isna(value) or value == '':
            return value

        elements = [element.strip() for element in str(value).split(",") if element.strip()]
        fixed_elements = [f"{url}{element}" for element in elements]
        return " | ".join(fixed_elements)

    try:
        df['associatedMedia'] = df['associatedMedia'].apply(fix_value)
        logging.info("addprefix_associatedmedia transformation completed successfully.")
    except Exception as e:
        logging.exception(f"An error occurred in addprefix_associatedmedia: {e}")
        raise

    return df


@register_transformation
def generate_occ_id_triplet(df):
    """
    Apply transformations creating occurrence IDs.

    Args:
        df (pd.DataFrame): Input DataFrame.

    Returns:
        pd.DataFrame: Transformed DataFrame.
    """
    try:
        # Create occurrenceID by combining multiple fields
        df['occurrenceID'] = (
            df['institutionCode']
            + ':'
            + df['collectionCode']
            + ':'
            + df['catalogNumber'].astype(str)
        )
        # Reorder columns to move 'occurrenceID' to the first position
        cols = ['occurrenceID'] + [col for col in df.columns if col != 'occurrenceID']
        df = df[cols]
        logging.info("DwC term occurrenceID addition completed successfully.")
        return df
    except Exception as e:
        logging.exception(f"An unexpected error occurred in generate_occ_id_triplet: {e}")
        raise


def format_time(row):
    if pd.isna(row):
        return None  # or you can return "00:00:00" or any default value
    else:
        td = pd.to_timedelta(row)
        components = td.components
        return f"{int(components.hours):02}:{int(components.minutes):02}:{int(components.seconds):02}"


@register_transformation
def format_eventTime(df):
    df['eventTime'] = df['eventTime'].apply(format_time)
    return df

@register_transformation
def add_individualcount(df):
    if "quantity_min" not in df.columns:
        raise KeyError("Column 'quantity_min' is required for add_individualcount.")
    df['individualCount'] = df['quantity_min'].fillna('')
    return df


@register_transformation
def vernacular_to_scientificName(df, config):
    """
    Converts vernacular names to scientific names and taxon ranks based on the provided JSON configuration.

    Args:
        df (pandas.DataFrame): The DataFrame containing the 'vernacularName' column.
        config (dict): : Configuration dictionary containing 'vernacular_to_scientificName',
                           a dictionary mapping vernacular names to scientific names and taxon rank.

    Returns:
        pandas.DataFrame: The modified DataFrame with additional 'scientificName' and 'taxonRank' columns.

    Raises:
        KeyError: If the 'vernacular_to_scientificName' key is missing from the config JSON.
        json.JSONDecodeError: If the config JSON is not properly formatted.
    """
    try:
        # Ensure the expected key is in the parsed JSON config
        vernacular_dict = config['vernacular_to_scientificName']

        # Create dictionaries mapping vernacular names to scientific names and taxon ranks
        scientific_name_map = {
            key: value['scientificName'] for key, value in vernacular_dict.items()
        }
        taxon_rank_map = {key: value['taxonRank'] for key, value in vernacular_dict.items()}

        # Map vernacular names to scientific names and taxon ranks in the DataFrame
        df['scientificName'] = df['vernacularName'].map(scientific_name_map)
        df['taxonRank'] = df['vernacularName'].map(taxon_rank_map)

        logging.info("DwC terms scientificName and taxonRank addition completed successfully.")
        return df

    except KeyError as exc:
        raise KeyError(
            "The 'vernacular_to_scientificName' key is missing from the configuration."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError("The configuration JSON is not properly formatted.") from exc


@register_transformation
def convert_column_to_int(df, columnname):
    """
    Convert the specified column in a DataFrame to nullable integer (Int64) type,
    keeping blank values as blank (NaN).

    Parameters:
    df (pd.DataFrame): The input DataFrame.
    columnname (str): The name of the column to be converted to nullable integer type.

    Returns:
    pd.DataFrame: DataFrame with the specified column converted to nullable integers (Int64).
    """
    # Ensure the column exists in the DataFrame
    if columnname in df.columns:
        # Convert the column to integer while preserving NaN values
        df[columnname] = pd.to_numeric(df[columnname], errors='coerce').astype("Int64")
    else:
        logging.info(f"Column '{columnname}' does not exist in the DataFrame.")

    logging.info(f"Column '{columnname}' converted to integer.")
    return df


def apply_transformations(df, config):
    df = df.copy()
    try:
        # Rename columns
        df.rename(columns=config.get('mapping', {}), inplace=True)

        # Fill default values
        for col, default_value in config.get('defaults', {}).items():
            if col in df.columns:
                df[col] = df[col].fillna(default_value)
            else:
                df[col] = default_value

        # Apply transformations
        transformations = config.get('transformations', [])
        for transformation in transformations:
            func_name = transformation.get('function')
            params = transformation.get('params', {})

            # Call transformation function dynamically
            function = TRANSFORMATION_REGISTRY.get(func_name)
            if function is None:
                raise ValueError(f"Unknown transformation function: {func_name}")
            validate_transformation_requirements(df, func_name, config)
            if func_name in CONFIG_AWARE_TRANSFORMATIONS:
                df = function(df, config)
            else:
                df = function(df, **params)

        return df
    except Exception as e:
        logging.error(f"An error occurred during transformation: {e}")
        raise
