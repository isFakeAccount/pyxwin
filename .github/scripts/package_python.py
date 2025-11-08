#!/usr/bin/env python3
"""Copies Python development files (headers, libs and dlls) into a structured directory for uploading to github artifacts."""

from __future__ import annotations

import argparse
import shutil
import sys
import sysconfig
from pathlib import Path


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Package Python dev files into a zip archive.")
    parser.add_argument("--python-version", "-p", required=True, help="Python version (e.g., 3.12.0)")
    parser.add_argument("--arch", "-a", required=True, help="Architecture (e.g., x64, arm64)")
    args = parser.parse_args()

    prefix = Path(sys.prefix)
    include_dir = Path(sysconfig.get_path("include"))
    libs_dir = prefix / "libs"

    dlls = [
        f"python{sys.version_info.major}.dll",  # stable ABI (abi3)
        f"python{sys.version_info.major}{sys.version_info.minor}.dll",  # full ABI
    ]
    dll_paths = [prefix / dll_name for dll_name in dlls]

    dest_root = Path(f"dist/python-{args.python_version}-{args.arch}-windows")
    dest_root.mkdir(parents=True, exist_ok=True)

    # Copy Include and libs
    print(f"[INFO] Copying Include -> {dest_root / 'Include'}")
    shutil.copytree(include_dir, dest_root / "Include", dirs_exist_ok=True)

    print(f"[INFO] Copying libs -> {dest_root / 'libs'}")
    shutil.copytree(libs_dir, dest_root / "libs", dirs_exist_ok=True)

    # Copy DLLs
    for dll_path in dll_paths:
        if dll_path.exists():
            print(f"[INFO] Copying DLL -> {dll_path.name}")
            shutil.copy2(dll_path, dest_root / dll_path.name)
        else:
            print(f"[WARN] DLL not found: {dll_path}")


if __name__ == "__main__":
    main()
