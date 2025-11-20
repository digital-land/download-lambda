# Development Setup

## Quick Start

1. **Install development dependencies:**
   ```bash
   make install-dev
   ```

   This will:
   - Install the `src/` package in editable mode (allows imports without `sys.path` hacks)
   - Install all development dependencies (pytest, flake8, black, mypy, etc.)

2. **Run tests:**
   ```bash
   make test           # Run all tests
   make test-unit      # Run only unit tests
   make lint           # Run linting checks
   make format         # Auto-format code
   ```

## Project Structure

The project uses `pyproject.toml` for modern Python packaging:
- Source code is in `src/`
- Tests import directly from `src/` (no `sys.path` manipulation needed)
- Install with `pip install -e .` for development

## Why Editable Install?

Installing the package in editable mode (`pip install -e .`) allows:
- ✅ Clean imports: `from lambda_function import ...`
- ✅ No `sys.path.insert()` hacks
- ✅ IDE auto-completion works properly
- ✅ Flake8 doesn't complain about import errors
- ✅ Tests run the same way in dev and CI

## Linting

The project uses:
- **Flake8**: Python code linter (style and errors)
- **Black**: Code formatter (auto-fixes formatting)
- **MyPy**: Static type checker

Run all checks:
```bash
make lint
```

Auto-fix formatting issues:
```bash
make format
```
