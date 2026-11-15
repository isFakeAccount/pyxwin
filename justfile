# Justfile for project tasks

default:
    just --choose

ls:
    just --list

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

# Runs all tasks
all: static fmt
