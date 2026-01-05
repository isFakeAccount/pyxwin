#!/usr/bin/env python3
"""Copies Python development files (headers, libs and dlls) into a structured directory for uploading to github artifacts."""

from __future__ import annotations

import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
from os import cpu_count
from pathlib import Path


def get_uv_python_dirs() -> list[Path]:
    """Get paths of all the python installations by uv."""
    result = subprocess.run(["uv", "python", "dir"], capture_output=True, text=True, check=True)  # noqa: S607
    python_dir = Path(result.stdout.strip())
    cpython_installation_dirs = python_dir.glob("cpython-*")
    return list(cpython_installation_dirs)


def copy_python_dev_files(src_dir: Path, dest_root: Path) -> None:
    """Copy Python development files from src_dir to dest_root."""
    include_dir = src_dir / "include"
    libs_dir = src_dir / "libs"
    dlls = src_dir.glob("python*.dll")
    dll_paths = [src_dir / dll_name for dll_name in dlls]

    dest_root.mkdir(parents=True, exist_ok=True)

    # Copy include and libs
    print(f"[INFO] Copying include -> {dest_root / 'include'}")
    shutil.copytree(include_dir, dest_root / "include", dirs_exist_ok=True)

    print(f"[INFO] Copying libs -> {dest_root / 'libs'}")
    shutil.copytree(libs_dir, dest_root / "libs", dirs_exist_ok=True)

    # Copy DLLs
    for dll_path in dll_paths:
        if dll_path.exists():
            print(f"[INFO] Copying DLL -> {dll_path.name}")
            shutil.copy2(dll_path, dest_root / dll_path.name)
        else:
            print(f"[WARN] DLL not found: {dll_path}")


def main() -> None:
    """Entry point."""
    cpython_installation_dirs = get_uv_python_dirs()

    num_cores = cpu_count() or 1
    with ProcessPoolExecutor(max_workers=num_cores * 2) as executor:
        for cpython_dir in cpython_installation_dirs:
            dest_root = Path("dist") / cpython_dir.name
            executor.submit(copy_python_dev_files, cpython_dir, dest_root)


if __name__ == "__main__":
    main()
