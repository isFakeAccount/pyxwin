"""Provides functions to extract Microsoft CRT and SDK files."""

from __future__ import annotations

import asyncio
import concurrent.futures
import shutil
from typing import TYPE_CHECKING
from zipfile import ZipFile

from pymsi import Msi as pymsi_Msi
from pymsi.package import Package as PyMSI_Package

if TYPE_CHECKING:
    from pathlib import Path

    from pymsi.msi.directory import Directory
    from pymsi.thirdparty.refinery.cab import CabFolder

    from pyxwin.wincrt_sdk.manifest_datatypes import ManifestOptions


def _build_output_directory(output: Path, folder_name: str) -> Path:
    """Helps build a more sane output directory for the SDK files.

    Typically, the full path to a file would be something like `Program Files/Windows Kits/10/Lib/10.0.19041.0/um/x64`.
    The goal is to reduce it a bit to something like `output/lib/um/x64` instead.

    :param output: The root directory where files are going to be extracted.
    :param folder_name: The name of the folder being currently processed.

    :returns: The path to the output directory where the files will be extracted.

    """
    if folder_name in ("Include", "Lib", "Source"):
        # Use lowercase for these like sane people.
        folder_name = folder_name.lower()
        output_path_bld = output / folder_name
    elif folder_name[0].isdigit() or folder_name.isdigit():
        # Skips the versioned folders like 10.0.10240.0, 10, 11, etc.
        output_path_bld = output
    elif folder_name in ("ProgramFilesFolder", "Windows Kits"):
        # Skip these directories in final path.
        output_path_bld = output
    else:
        output_path_bld = output / folder_name
    return output_path_bld


# These directories are not needed for CRT/SDK extraction.
DIRS_TO_SKIP = (
    "AccChecker",
    "AccScope",
    "AppPerfAnalyzer",
    "Catalogs",
    "DesignTime",
    "en-US",
    "SecureBoot",
    "UIAVerify",
    "XamlDiagnostics",
)


def _extract_root(root: Directory, output: Path, is_root: bool = True) -> None:
    """Recursively iterates through the MSI directory structure and extracts files.

    :param root: The MSI root directory to extract files from.
    :param output: The directory to extract the files to.
    :param is_root: Whether this is the root directory, defaults to True

    """
    # Improve this later. Need to look into the MSI format and the pymsi library.
    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)

    for component in root.components.values():
        for file in component.files.values():
            try:
                cab_file = file.resolve()
                output_file_path = output / file.name
                output_file_path.write_bytes(cab_file.decompress())
            except ValueError:
                # Not sure why it is not able to resolve some files
                # but at the end the files are still extracted correctly.
                continue

    for child in root.children.values():
        folder_name = child.name
        if is_root:
            if "." in child.id:
                folder_name, guid = child.id.split(".", 1)
                if child.id != folder_name:
                    print(f"Warning: Directory ID '{child.id}' has a GUID suffix ({guid}).")
            else:
                folder_name = child.id

        if folder_name in DIRS_TO_SKIP:
            continue

        output_path_bld = _build_output_directory(output, folder_name)
        _extract_root(child, output_path_bld, False)


def _extract_msi(file_path: Path, extract_location: Path) -> None:
    """Extracts an MSI file to the specified location.

    :param file_path: The path to the MSI file.
    :param extract_location: The directory to extract the MSI file to.

    """
    with PyMSI_Package(file_path) as package:
        msi = pymsi_Msi(package, load_data=True)

    # Improve this later. Need to look into the MSI format and the pymsi library.
    folders: list[CabFolder] = []
    for media in msi.medias.values():
        if media.cabinet and media.cabinet.disks:
            for disk in media.cabinet.disks.values():
                for directory in disk:
                    for folder in directory.folders:
                        if folder not in folders:
                            folders.append(folder)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for folder in folders:
            executor.submit(folder.decompress)

    _extract_root(msi.root, extract_location)


async def multi_extract_msi_async(files: list[tuple[Path, Path]]) -> None:
    """Extracts multiple MSI files concurrently.

    :param files: A list of tuples containing (file_path, extract_location) for each file.

    """
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        tasks: list[asyncio.Future[None]] = []
        for file_path, extract_location in files:
            task = loop.run_in_executor(executor, _extract_msi, file_path, extract_location)
            tasks.append(task)
        await asyncio.gather(*tasks)


def _extract_vsix(file_path: Path, extract_location: Path) -> None:
    """Extracts a VSIX file to the specified location.

    :param file_path: The path to the VSIX file.
    :param extract_location: The directory to extract the VSIX file to.

    """
    required_dirs = ("lib", "src", "include", "crt")

    with ZipFile(file_path, "r") as zip_ref:
        files_to_extract = [
            archive_path
            for archive_path in zip_ref.namelist()  # Force line break
            if any(required_dir in archive_path for required_dir in required_dirs)  # Force line break
        ]
        zip_ref.extractall(extract_location, files_to_extract)


async def multi_extract_vsix_async(files: list[tuple[Path, Path]]) -> None:
    """Extracts multiple VSIX files concurrently.

    :param files: A list of tuples containing (file_path, extract_location) for each file.

    """
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        tasks: list[asyncio.Future[None]] = []
        for file_path, extract_location in files:
            task = loop.run_in_executor(executor, _extract_vsix, file_path, extract_location)
            tasks.append(task)
        await asyncio.gather(*tasks)


async def reduce_crt_files(crt_packages_dir: Path, manifest_options: ManifestOptions) -> None:
    """Reduces the extracted SDK and CRT files to only those necessary.

    :param sdk_packages_dir: The directory where SDK packages are extracted.
    :param crt_packages_dir: The directory where CRT packages are extracted.
    :param manifest_options: The manifest options used for extraction.

    """
    crt_out_dir = manifest_options.cache_dir / "reduced" / crt_packages_dir.name
    crt_subdirectories = {
        "include": crt_out_dir / "include",
        "lib": crt_out_dir / "lib",
        "src": crt_out_dir / "src",
        "crt": crt_out_dir / "crt",
    }
    for d in crt_subdirectories.values():
        d.mkdir(parents=True, exist_ok=True)

    from_dirs: list[Path] = []
    for p in crt_packages_dir.rglob("*"):
        if not p.is_dir() or p.name not in crt_subdirectories:
            continue
        from_dirs.append(p)

    for from_dir in from_dirs:
        to_dir = crt_subdirectories[from_dir.name]
        shutil.copytree(from_dir, to_dir, dirs_exist_ok=True)


async def reduce_sdk_files(sdk_packages_dir: Path, manifest_options: ManifestOptions) -> None:
    """Reduces the extracted SDK files to only those necessary.

    :param sdk_packages_dir: The directory where SDK packages are extracted.
    :param manifest_options: The manifest options used for extraction.

    """
    sdk_out_dir = manifest_options.cache_dir / "reduced" / sdk_packages_dir.name
    sdk_subdirectories = {
        "include": sdk_out_dir / "include",
        "lib": sdk_out_dir / "lib",
        "source": sdk_out_dir / "source",
        "bin": sdk_out_dir / "bin",
    }
    for d in sdk_subdirectories.values():
        d.mkdir(parents=True, exist_ok=True)

    from_dirs: list[Path] = []
    for p in sdk_packages_dir.rglob("*"):
        if not p.is_dir() or p.name not in sdk_subdirectories:
            continue
        from_dirs.append(p)

    for from_dir in from_dirs:
        to_dir = sdk_subdirectories[from_dir.name]
        shutil.copytree(from_dir, to_dir, dirs_exist_ok=True)


async def reduce_sdk_crt_files(sdk_packages_dir: Path, crt_packages_dir: Path, manifest_options: ManifestOptions) -> None:
    """Reduces the extracted SDK and CRT files to only those necessary."""
    async with asyncio.TaskGroup() as tg:
        tg.create_task(reduce_sdk_files(sdk_packages_dir, manifest_options))
        tg.create_task(reduce_crt_files(crt_packages_dir, manifest_options))
