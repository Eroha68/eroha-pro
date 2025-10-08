# eroha-pro

## Overview
This is a Python CI/CD infrastructure project that provides testing and linting configuration for Python projects. It's set up with modern Python tooling including pytest, ruff, black, and isort.

## Project Structure
- `tests/` - Test directory containing test files
- `pyproject.toml` - Configuration for ruff, black, isort, and pytest
- `requirements.txt` - Python dependencies
- `.github/workflows/ci.yml` - GitHub Actions CI configuration

## Setup on Replit
The project has been configured to run in the Replit environment with:
- Python 3.10 installed
- All dependencies from requirements.txt installed
- A workflow configured to run pytest tests

## Running Tests
Tests run automatically via the "Tests" workflow. You can also run them manually:
```bash
pytest -q
```

## Linting and Formatting
The project includes several code quality tools:
- **Ruff**: Fast Python linter
  ```bash
  ruff check .
  ruff format --check .
  ```
- **Black**: Code formatter
  ```bash
  black --check .
  ```
- **isort**: Import sorting
  ```bash
  isort . --check-only --diff
  ```

## Recent Changes
- **2025-10-08**: Initial Replit setup
  - Installed Python 3.10 and dependencies
  - Created tests directory with basic smoke tests
  - Configured pytest workflow
  - Added Python .gitignore rules

## Architecture
This is a minimal Python project focused on CI/CD infrastructure:
- Uses pytest for testing with coverage support
- Configured with modern Python linting tools (ruff, black, isort)
- GitHub Actions workflow for automated testing
- Python 3.10 target version

## Dependencies
- pytest & pytest-cov: Testing framework and coverage
- ruff: Fast Python linter
- black: Code formatter
- isort: Import statement organizer
