# Justfile for project tasks

default:
    just --choose

# Format the Justfile
just-fmt:
    just --fmt --unstable

# Run code and docstring formatting and linter
fmt:
    poetry run docstrfmt src/
    poetry run ruff format src/
    poetry run ruff check src/ --fix

# Run static analysis and linting
static:
    poetry run mypy src/
    poetry run pyright src/

# Build and check documentation
docs:
    cd docs && make apidoc
    cd docs && make clean
    cd docs && make html
    cd docs && make linkcheck

# Run unit tests
unit:
    poetry run pytest --cov-config=pyproject.toml

# Runs all tasks
all: static fmt docs unit
