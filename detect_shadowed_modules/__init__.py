#!/usr/bin/env python3
"""
Detect conflicting directory names across Python's sys.path.

When Python imports a module, it searches directories in sys.path order. If the
same directory name exists in multiple sys.path entries, only the first one is
used—potentially shadowing packages you intended to import. This script identifies
such conflicts to help diagnose import issues.

Example conflict scenario:
    sys.path = ['/project', '/usr/lib/python3/site-packages']

    If both contain a 'requests/' directory:
      - /project/requests/          <- This shadows the real package
      - /usr/lib/python3/site-packages/requests/

    Importing 'requests' will use /project/requests/, not the installed package.

Usage:
    detect-shadowed-modules          # Print conflicts to stdout
    detect-shadowed-modules -q       # Quiet mode (conflicts only)
    detect-shadowed-modules --json   # Output as JSON
"""

import argparse
import importlib.metadata
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

from detect_shadowed_modules.editable import get_editable_paths

logger = logging.getLogger(__name__)


def setup_logging(quiet: bool = False) -> None:
    """Configure logging with appropriate verbosity."""
    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def get_subdirectories(path: Path) -> list[str]:
    """
    Get immediate subdirectory names, excluding hidden dirs, __pycache__, and metadata dirs.

    Args:
        path: Directory to scan.

    Returns:
        List of subdirectory names (not full paths).
    """
    if not path.is_dir():
        logger.debug(f"Skipping non-directory: {path}")
        return []

    subdirs = []
    try:
        for entry in path.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            # Skip hidden dirs, __pycache__, and package metadata dirs
            if (
                name.startswith(".")
                or name == "__pycache__"
                or name.endswith(".dist-info")
                or name.endswith(".egg-info")
            ):
                logger.debug(f"  Skipping: {name}/")
                continue
            subdirs.append(name)
            logger.debug(f"  Found: {name}/")
    except PermissionError:
        logger.warning(f"Permission denied: {path}")
    except OSError as e:
        logger.warning(f"Error accessing {path}: {e}")

    return subdirs


def find_package_owner(directory_name: str) -> str | None:
    """
    Find the installed distribution that provides a top-level package name.

    Args:
        directory_name: The name of the directory (e.g., 'requests', 'numpy').

    Returns:
        Package name if found, None otherwise.
    """
    try:
        # Try to find a distribution that provides this top-level name
        # This works for most packages where the directory name matches the package
        dist = importlib.metadata.distribution(directory_name)
        return dist.metadata["Name"]
    except importlib.metadata.PackageNotFoundError:
        pass

    # Fallback: check top_level.txt in all distributions
    for dist in importlib.metadata.distributions():
        try:
            top_level = dist.read_text("top_level.txt")
            if top_level and directory_name in top_level.strip().split("\n"):
                return dist.metadata["Name"]
        except FileNotFoundError:
            continue

    return None


def find_package_owner_by_path(directory: Path) -> str | None:
    """
    Find the installed distribution that owns files in a specific directory.

    This is slower but more accurate for directories that don't match their
    package name (e.g., a 'tests/' dir installed by some package).

    Args:
        directory: Full path to the directory.

    Returns:
        Package name if found, None otherwise.
    """
    directory = directory.resolve()

    for dist in importlib.metadata.distributions():
        for f in dist.files or []:
            try:
                full = dist.locate_file(f)
                if full:
                    full_path = Path(str(full)).resolve()
                    # Check if this file is inside the directory we're looking for
                    if directory in full_path.parents or full_path.parent == directory:
                        return dist.metadata["Name"]
            except (OSError, ValueError):
                continue

    return None


def find_conflicts(paths: list[str] | None = None) -> dict[str, list[Path]]:
    """
    Find directory names that appear in multiple sys.path locations.

    Args:
        paths: List of paths to check. Defaults to sys.path.

    Returns:
        Dict mapping conflicting directory names to the paths containing them.
    """
    if paths is None:
        paths = sys.path

    dir_locations: dict[str, list[Path]] = defaultdict(list)

    for path_str in paths:
        # Empty string means current working directory
        path = Path(path_str or os.getcwd()).resolve()

        for subdir in get_subdirectories(path):
            dir_locations[subdir].append(path)

    # Keep only directories appearing in multiple locations
    return {name: locs for name, locs in dir_locations.items() if len(locs) > 1}


def format_report(
    conflicts: dict[str, list[Path]],
    searched_paths: list[str] | None = None,
    editable_paths: set[str] | None = None,
) -> str:
    """
    Format conflicts as a human-readable report.

    Args:
        conflicts: Dict mapping conflicting directory names to their locations.
        searched_paths: List of paths that were searched. Shown when conflicts exist.
        editable_paths: Set of paths that are editable packages.
    """
    # ANSI color codes
    green = "\033[92m"
    red = "\033[91m"
    yellow = "\033[93m"
    cyan = "\033[96m"
    reset = "\033[0m"

    if not conflicts:
        return f"{green}No conflicting directory names found{reset}"

    lines = [
        f"{red}Conflicting directory names detected:{reset}",
        "",
        "These directories exist in multiple sys.path locations. The first",
        "location listed will shadow the others during import.",
        "",
    ]

    for name in sorted(conflicts):
        locations = conflicts[name]
        owner = find_package_owner(name)
        lines.append(f"  {name}/")
        for i, loc in enumerate(locations):
            full_path = loc / name
            prefix = "  → " if i == 0 else "    "
            suffix = " (shadows others)" if i == 0 else " (shadowed)"
            owner_info = f" [{owner}]" if owner and i > 0 else ""
            lines.append(f"{prefix}{full_path}{owner_info}{suffix}")
        lines.append("")

    # Add searched directories section when conflicts exist
    if searched_paths and editable_paths is not None:
        lines.append(
            f"{yellow}Searched directories ({len(searched_paths)} total):{reset}"
        )
        for path_str in searched_paths:
            is_editable = path_str in editable_paths
            marker = f" {cyan}[editable]{reset}" if is_editable else ""
            lines.append(f"  {path_str}{marker}")
        lines.append("")

    return "\n".join(lines)


def format_json(
    conflicts: dict[str, list[Path]],
    searched_paths: list[str] | None = None,
    editable_paths: set[str] | None = None,
) -> str:
    """
    Format conflicts as JSON, including shadowed directories and what shadows them.

    Args:
        conflicts: Dict mapping conflicting directory names to their locations.
        searched_paths: List of paths that were searched.
        editable_paths: Set of paths that are editable packages.
    """
    shadowed = []

    for name, locations in conflicts.items():
        shadowing_path = locations[0] / name
        # Try fast name-based lookup first, fall back to slower path-based lookup
        owner = find_package_owner(name)
        if owner is None:
            owner = find_package_owner_by_path(shadowing_path)

        # Skip the first location (it's the one doing the shadowing)
        for loc in locations[1:]:
            full_path = loc / name
            shadowed.append(
                {
                    "path": str(full_path),
                    "shadowed_by": str(shadowing_path),
                    "owner": owner,
                }
            )

    result = {"shadowed": shadowed}

    # Add searched paths information
    if searched_paths is not None and editable_paths is not None:
        result["searched_paths"] = [
            {
                "path": path_str,
                "editable": path_str in editable_paths,
            }
            for path_str in searched_paths
        ]

    return json.dumps(result, indent=2)


def main() -> int:
    """Main entry point. Returns exit code (0=no conflicts, 1=conflicts found)."""
    parser = argparse.ArgumentParser(
        description="Detect conflicting directory names in sys.path.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode: only show conflicts, not scanning progress",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )
    args = parser.parse_args()

    setup_logging(quiet=args.quiet or args.json_output)

    # Get editable package paths
    editable_paths_list = get_editable_paths()
    logger.debug(f"Found {len(editable_paths_list)} editable package(s)")

    # Track which paths are editable (as strings for easy comparison)
    editable_paths_set = {str(p) for p in editable_paths_list}

    # Combine editable paths with sys.path (editable paths first, then deduplicate)
    combined_paths = [str(p) for p in editable_paths_list] + sys.path
    # Deduplicate while preserving order
    seen = set()
    unique_paths = []
    for path in combined_paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)

    logger.debug("Scanning sys.path for directory conflicts...")
    conflicts = find_conflicts(unique_paths)

    if args.json_output:
        print(format_json(conflicts, unique_paths, editable_paths_set))
    else:
        print(format_report(conflicts, unique_paths, editable_paths_set))

    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
