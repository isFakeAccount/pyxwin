#!/usr/bin/env python3
"""Script to download python using uv."""

from __future__ import annotations

import subprocess
from concurrent.futures import ProcessPoolExecutor
from os import cpu_count


def list_available_versions() -> list[str]:
    """Gets the list of available python version using the ``uv python list`` command."""
    result = subprocess.run(
        ["uv", "python", "list", "--all-platforms", "--all-arches"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )

    raw_lines = result.stdout.splitlines()
    cpython_versions = [raw_line.split()[0] for raw_line in raw_lines if raw_line.startswith("cpython")]
    return [version for version in cpython_versions if "windows" in version]


def install_python_version(python_version: str) -> None:
    """Installs the given python version using uv."""
    print(f"Installing {python_version}...")
    subprocess.run(["uv", "python", "install", python_version], check=True)  # noqa: S607


def main() -> None:
    """Entry point."""
    cpython_versions = list_available_versions()

    num_cores = cpu_count() or 1
    with ProcessPoolExecutor(max_workers=num_cores * 4) as executor:
        for cpython_version in cpython_versions:
            executor.submit(install_python_version, cpython_version)


if __name__ == "__main__":
    main()
