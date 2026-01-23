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

Searched directories (50 total):
  /home/user/myproject [editable]
  /home/user/.venv/lib/python3.13/site-packages
  /usr/lib/python3/site-packages
  ...
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
  ],
  "searched_paths": [
    {
      "path": "/home/user/myproject",
      "editable": true
    },
    {
      "path": "/home/user/.venv/lib/python3.13/site-packages",
      "editable": false
    },
    {
      "path": "/usr/lib/python3/site-packages",
      "editable": false
    }
  ]
}
```

## How It Works

The tool scans all directories in `sys.path` and:
1. Automatically detects editable packages installed via `uv` (using `uv pip list -e`)
2. Combines editable package paths with `sys.path` (editable paths take precedence)
3. Identifies subdirectories in each path
4. Detects when the same directory name appears in multiple locations
5. Reports which packages are being shadowed and by what
6. Attempts to identify the installed package that owns each directory

Excluded from scanning:
- Hidden directories (starting with `.`)
- `__pycache__` directories
- Package metadata directories (`.dist-info`, `.egg-info`)

## Debugging Import Issues

If you suspect a module is being imported from the wrong location, you can check where Python is actually loading it from:

```bash
python -c 'import <module>; print(<module>.__file__)'
```

For example:
```bash
python -c 'import requests; print(requests.__file__)'
# Output: /home/user/myproject/requests/__init__.py
```

This will show you the exact file path Python is using for the import, helping you confirm if shadowing is occurring.

## Exit Codes

- `0`: No conflicts found
- `1`: Conflicts detected

This makes it easy to use in CI/CD pipelines or pre-commit hooks.

## [MIT License](LICENSE.md)
