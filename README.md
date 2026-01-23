# detect-shadowed-modules

Detect conflicting directory names across Python's `sys.path` that may be shadowing your installed packages.

## Problem

When Python imports a module, it searches directories in `sys.path` order. If the same directory name exists in multiple `sys.path` entries, only the first one is used—potentially shadowing packages you intended to import. This can lead to confusing import errors and unexpected behavior.

### Example Conflict Scenario

```python
sys.path = ['/project', '/usr/lib/python3/site-packages']
```

If both paths contain a `requests/` directory:
- `/project/requests/` ← This shadows the real package
- `/usr/lib/python3/site-packages/requests/`

When you `import requests`, Python will use `/project/requests/` instead of the installed package, which is likely not what you want!

## Installation

```bash
uv add detect-shadowed-modules
```

Or, you can just use via uvx:

```sh
uvx detect-shadowed-modules@latest --help
```

## Usage

### Command Line

```bash
# Print conflicts to stdout with scanning progress
detect-shadowed-modules

# Quiet mode (conflicts only, no progress messages)
detect-shadowed-modules -q

# Output as JSON
detect-shadowed-modules --json
```

### As a Python Module

```python
import detect_shadowed_modules

# Find conflicts
conflicts = detect_shadowed_modules.find_conflicts()

# Generate a human-readable report
report = detect_shadowed_modules.format_report(conflicts)
print(report)

# Or get JSON output
json_output = detect_shadowed_modules.format_json(conflicts)
print(json_output)
```

## Output Examples

### Human-Readable Format

```
Conflicting directory names detected:

These directories exist in multiple sys.path locations. The first
location listed will shadow the others during import.

  requests/
  → /home/user/myproject/requests (shadows others)
    /usr/lib/python3/site-packages/requests [requests] (shadowed)
```

### JSON Format

```json
{
  "shadowed": [
    {
      "path": "/usr/lib/python3/site-packages/requests",
      "shadowed_by": "/home/user/myproject/requests",
      "owner": "requests"
    }
  ]
}
```

## How It Works

The tool scans all directories in `sys.path` and:
1. Identifies subdirectories in each path
2. Detects when the same directory name appears in multiple locations
3. Reports which packages are being shadowed and by what
4. Attempts to identify the installed package that owns each directory

Excluded from scanning:
- Hidden directories (starting with `.`)
- `__pycache__` directories
- Package metadata directories (`.dist-info`, `.egg-info`)

## Exit Codes

- `0`: No conflicts found
- `1`: Conflicts detected

This makes it easy to use in CI/CD pipelines or pre-commit hooks.

## [MIT License](LICENSE.md)
