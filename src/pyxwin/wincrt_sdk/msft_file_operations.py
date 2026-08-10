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

    from pyxwin.wincrt_sdk.manifest_datatypes import VisualStudioInstallerOptions


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
    else:
        output_path_bld = output / folder_name
    return output_path_bld


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
                folder_name, _ = child.id.split(".", 1)
            else:
                folder_name = child.id

        output_path_bld = _build_output_directory(output, folder_name)
        _extract_root(child, output_path_bld, False)


def should_extract_package(file_path: Path) -> bool:
    """Whether this MSI's payload is relevant to compiling/linking a full Win32 app."""
    name = file_path.stem

    return "headers" in name.lower() or "libs" in name.lower()


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


def _copy_tree(src: Path, dst: Path) -> None:
    """Copies a directory tree, replacing dst entirely if it already exists. Preserves symlinks."""
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)


def reduce_unpacked_files(unpacked_dir: Path, manifest_options: VisualStudioInstallerOptions) -> None:
    """Reduces the unpacked dir to essential files for compiling/linking."""
    reduce_dir = manifest_options.cache_dir / "reduce" / f"manifest_{manifest_options.manifest_version}" / manifest_options.channel

    msvc_dirs = unpacked_dir.glob("VC/Tools/MSVC/*")
    for msvc_dir in msvc_dirs:
        msvc_version = msvc_dir.name
        msvc_out = reduce_dir / f"msvc-{msvc_version}"

        _copy_tree(msvc_dir / "include", msvc_out / "include")
        _copy_tree(msvc_dir / "lib", msvc_out / "lib")

        if (msvc_dir / "atlmfc").exists():
            _copy_tree(msvc_dir / "atlmfc" / "include", msvc_out / "atlmfc" / "include")
            _copy_tree(msvc_dir / "atlmfc" / "lib", msvc_out / "atlmfc" / "lib")

    sdk_root = unpacked_dir / "ProgramFilesFolder" / "Windows Kits" / "10"
    sdk_include_dirs = list((sdk_root / "include").glob("*"))

    for sdk_include_dir in sdk_include_dirs:
        sdk_version = sdk_include_dir.name
        sdk_lib_dir = sdk_root / "lib" / sdk_version
        sdk_out = reduce_dir / f"sdk-{sdk_version}"

        _copy_tree(sdk_include_dir, sdk_out / "include")
        _copy_tree(sdk_lib_dir, sdk_out / "lib")
