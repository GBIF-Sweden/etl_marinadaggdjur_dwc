import json

import pandas as pd
import yaml

from tumlaretogbif.config.config_loader import load_config_file, validate_etl_config
from tumlaretogbif.transformation.transform import apply_transformations


def test_seal_config_loads_and_validates():
    config = load_config_file("etl_configs/seal.yml")
    validate_etl_config(config)
    assert config["load"]["database_table"] == "simpledwc_seals"


def test_seal_transformation_smoke_path():
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "observation_date": "2024-01-01",
                "seal_type": "gråsäl",
                "latitude": "60.0",
                "longitude": "18.0",
                "quantity": 2,
                "length": "200",
                "county": "Stockholm",
                "animal_decomposition_state": "Fresh",
                "updated_at": "2024-01-02",
                "associatedMedia": "seal1.jpg,seal2.jpg",
            }
        ]
    )
    config = load_config_file("etl_configs/seal.yml")
    transformed = apply_transformations(df, config)

    assert transformed.loc[0, "occurrenceID"] == "NRM:Seals:1"
    assert transformed.loc[0, "scientificName"] == "Halichoerus grypus (Fabricius, 1791)"
    assert json.loads(transformed.loc[0, "dynamicProperties"])["length"] == "200"
    assert "animal_decomposition_state" not in transformed.columns
    assert transformed.loc[0, "associatedMedia"] == (
        "https://marinadaggdjur.nrm.se/images/seal1.jpg | "
        "https://marinadaggdjur.nrm.se/images/seal2.jpg"
    )
