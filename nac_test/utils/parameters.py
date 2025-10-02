# -*- coding: utf-8 -*-

"""Parameter file utilities for learning/testing mode support.

This module provides utilities for saving and loading test parameters to/from JSON files,
enabling tests to run in "learning mode" (capture current state) or "testing mode"
(verify against previously captured state).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Union

logger = logging.getLogger(__name__)

# Type alias for parameter data
ParameterData = Dict[str, Any]


def save_parameters_to_file(
    data: ParameterData,
    parameters_file: Union[str, Path],
) -> bool:
    """Save test case parameters to a JSON file.

    Args:
        data: Data structure with parameters to save
        parameters_file: Path to the JSON file where parameters will be saved

    Returns:
        bool: True if successful, False otherwise

    Raises:
        Exception: If file writing fails
    """
    logger.info(f"Saving test case parameters to file '{parameters_file}'")

    # Ensure parent directory exists
    parameters_path = Path(parameters_file)
    parameters_path.parent.mkdir(parents=True, exist_ok=True)

    # Write parameters to JSON file
    try:
        with open(str(parameters_file), "w") as f:
            json.dump(data, f, indent=4)
            # Add newline to the end to make pre-commit hooks happy
            f.write("\n")
        logger.info(f"Successfully saved parameters to file '{parameters_file}'")
        return True
    except Exception as e:
        logger.error(f"Failed to write parameters to file '{parameters_file}': {e}")
        raise


def load_parameters_from_file(parameters_file: Union[str, Path]) -> ParameterData:
    """Load test case parameters from JSON file.

    Args:
        parameters_file: Path to the JSON file containing parameters

    Returns:
        ParameterData: Data structure with parameters loaded from file,
                      or empty dict if file doesn't exist or loading fails
    """
    logger.info(f"Loading parameters from file '{parameters_file}'")

    parameters_path = (
        Path(parameters_file)
        if not isinstance(parameters_file, Path)
        else parameters_file
    )

    if not parameters_path.exists():
        logger.warning(f"Parameters file '{parameters_file}' not found")
        return {}

    try:
        with open(str(parameters_path), "r") as f:
            parameters: ParameterData = json.load(f)
        logger.info(f"Successfully loaded parameters from file '{parameters_file}'")
        return parameters
    except Exception as e:
        logger.error(f"Failed to load parameters file '{parameters_file}': {e}")
        return {}
