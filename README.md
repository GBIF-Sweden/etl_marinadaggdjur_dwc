# etl_marinadaggdjur_dwc

This repository is a phased migration of the `tumlaretogbif_src` ETL codebase into a new versioned repository.

## Overview

The migration is being performed incrementally in phases:

1. Repository base and test infrastructure
2. Core ETL engine and the `tumlare` pipeline
3. Second pipeline (`seal`)
4. Miscellaneous tooling and validation
5. Migration review

## Setup

Use a Python 3.12 environment and install base dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Running the ETL

The ETL runner will be added in later phases. At that point, the typical execution will be:

```bash
python -m etl_marinadaggdjur_dwc.main etl_configs/tumlare.yml
```

## Notes

- This repository is built from the `tumlaretogbif_src` source code.
- The source folder is treated as READ-ONLY during migration.
- Ansible files and symlinked data/log directories are excluded from migration.
