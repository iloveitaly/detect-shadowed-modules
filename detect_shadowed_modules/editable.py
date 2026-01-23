"""
Get paths to editable packages installed via uv.

This module provides functionality to discover editable package locations
by querying uv's package list.
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def get_editable_paths() -> list[Path]:
    """
    Get paths to editable packages by running uv pip list.

    Runs: uv pip list -e --format json

    The JSON output from uv looks like:
    [{"name":"pkg","version":"0.1.0","editable_project_location":"/path/to/pkg"}]

    Returns:
        List of paths from editable_project_location field.
        Returns empty list if uv is unavailable or fails.
    """
    try:
        result = subprocess.run(
            ["uv", "pip", "list", "-e", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.debug(f"uv pip list failed with code {result.returncode}")
            return []

        # Parse JSON output
        packages = json.loads(result.stdout)

        # Extract editable_project_location from each package
        paths = []
        for pkg in packages:
            if "editable_project_location" in pkg:
                path = Path(pkg["editable_project_location"])
                paths.append(path)
                logger.debug(f"Found editable package: {pkg.get('name')} at {path}")

        return paths

    except FileNotFoundError:
        # uv is not installed or not in PATH
        logger.debug("uv not found in PATH")
        return []
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse uv output as JSON: {e}")
        return []
    except subprocess.TimeoutExpired:
        logger.debug("uv pip list timed out")
        return []
    except Exception as e:
        logger.debug(f"Unexpected error getting editable paths: {e}")
        return []
