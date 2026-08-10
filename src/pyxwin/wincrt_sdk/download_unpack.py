"""Downloads and extracts Windows CRT and SDK packages."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from platform import system
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from pyxwin.core.aiofiles_wrapper import async_read_text, async_write_text, multi_download_and_validate
from pyxwin.wincrt_sdk.msft_file_operations import multi_extract_msi_async, multi_extract_vsix_async

if TYPE_CHECKING:
    from rich.progress import Progress

    from pyxwin.wincrt_sdk.manifest_datatypes import ManifestPayload, VisualStudioInstallerOptions


async def download_packages(
    manifest_options: VisualStudioInstallerOptions,
    workload_payloads: dict[str, dict[str, list[ManifestPayload]]],
    progress: Progress | None = None,
) -> list[Path]:
    """Downloads the specified Windows CRT and SDK packages to specific paths.

    :param workload_packages: A dictionary mapping architectures to lists of SDKPayload or CRTPayload objects
        representing the packages to download.

    """
    files_to_download: list[tuple[str, Path, str]] = []
    download_directory = manifest_options.cache_dir / "downloads" / f"manifest_{manifest_options.manifest_version}" / manifest_options.channel

    task_groups: list[asyncio.Task[list[tuple[str, Path, str]]]] = []
    async with asyncio.TaskGroup() as tg:
        for workload, workload_payloads_per_arch in workload_payloads.items():
            task_groups.append(tg.create_task(_download_workload(download_directory, workload, workload_payloads_per_arch, manifest_options.cache_dir)))

    for task in task_groups:
        files_to_download.extend(await task)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(multi_download_and_validate(files_to_download, max_concurrent=5, progress=progress))
        tg.create_task(_snapshot_workloads_state(download_directory, manifest_options.cache_dir, workload_payloads))

    return [x[1] for x in files_to_download]


async def _download_workload(
    download_directory: Path,
    workload: str,
    workload_payloads_per_arch: dict[str, list[ManifestPayload]],
    cache_dir: Path,
) -> list[tuple[str, Path, str]]:
    """Downloads the specified workload packages to specific paths.

    Triggers re-download if the file does not exist or if the SHA256 checksum does not match from upstream.

    :param download_directory: The path to the directory where the packages will be downloaded.
    :param workload: The name of the workload to download.
    :param workload_payloads_per_arch: A dictionary mapping architectures to lists of SDKPayload or CRTPayload objects
        representing the packages to download.

    :returns: A list of tuples containing (url, file_path, target_sha256) for each package that needs to be downloaded.

    """
    files_to_download: list[tuple[str, Path, str]] = []
    snapshot_dir = download_directory / "workload_snapshots"
    workload_snapshot_file = snapshot_dir / f"{workload}.json"

    workload_snapshot: dict[str, dict[str, dict[str, str]]] = {}
    if workload_snapshot_file.exists():
        workload_snapshot = json.loads(await async_read_text(workload_snapshot_file))

    for arch, packages in workload_payloads_per_arch.items():
        for package in packages:
            file_path = package.suggested_install_filepath(download_directory / workload / arch)
            relative_file_path = file_path.relative_to(cache_dir)

            stored_sha256 = workload_snapshot.get(arch, {}).get(file_path.name, {}).get("sha256")
            stored_path = workload_snapshot.get(arch, {}).get(file_path.name, {}).get("path")

            if stored_sha256 is None or stored_path is None:
                needs_download = True
            else:
                needs_download = not file_path.exists() or (stored_sha256 != package.sha256 and (stored_path != str(relative_file_path)))

            if needs_download:
                file_path.parent.mkdir(exist_ok=True, parents=True)
                files_to_download.append((package.url, file_path, package.sha256))

    return files_to_download


async def _snapshot_workloads_state(download_directory: Path, cache_dir: Path, workload_payloads: dict[str, dict[str, list[ManifestPayload]]]) -> None:
    """Creates a snapshot of the workloads state in a JSON file.

    :param download_directory: The path to the directory where the snapshot will be saved.
    :param workload_payloads: A dictionary mapping architectures to lists of SDKPayload or CRTPayload objects
        representing the packages to download.

    """
    snapshot_dir = download_directory / "workload_snapshots"
    snapshot_dir.mkdir(exist_ok=True, parents=True)
    for workload, workload_payloads_per_arch in workload_payloads.items():
        workload_data: dict[str, dict[str, dict[str, str]]] = {}
        for arch, packages in workload_payloads_per_arch.items():
            workload_data.setdefault(arch, {})
            for package in packages:
                workload_data[arch][package.file_name] = {
                    "path": str(package.suggested_install_filepath(download_directory / workload / arch).relative_to(cache_dir)),
                    "sha256": package.sha256,
                }

        await async_write_text(snapshot_dir / f"{workload}.json", json.dumps(workload_data, indent=4, sort_keys=True))


async def unpack_files(manifest_options: VisualStudioInstallerOptions, file_paths: list[Path]) -> None:
    """Unpacks downloaded Windows CRT and SDK packages.

    :param manifest_options: Stores the config options for fetching the Win CRT & SDK files.
    :param file_paths: A list of file paths to the downloaded packages.

    """
    vsix_file_paths: list[tuple[Path, Path]] = []
    msi_file_paths: list[tuple[Path, Path]] = []

    unpack_dir = manifest_options.cache_dir / "unpack" / f"manifest_{manifest_options.manifest_version}" / manifest_options.channel

    with TemporaryDirectory() as unpack_temp_dir:
        unpack_temp_dir_path = Path(unpack_temp_dir)
        for file_path in file_paths:
            file_name = file_path.name
            package_dir_name = file_path.parent.name

            # No need to unpack CAB files directly
            if file_name.endswith(".cab"):
                continue

            extract_location = unpack_temp_dir_path / package_dir_name / file_name
            extract_location.mkdir(exist_ok=True, parents=True)

            if file_path.suffix == ".vsix":
                vsix_file_paths.append((file_path, extract_location))
            elif file_path.suffix == ".msi":
                msi_file_paths.append((file_path, extract_location))

        async with asyncio.TaskGroup() as tg:
            tg.create_task(multi_extract_vsix_async(vsix_file_paths))
            tg.create_task(multi_extract_msi_async(msi_file_paths))

        _copy_unpacked_files(unpack_dir, unpack_temp_dir_path)

        if system() != "Windows":
            _symlink_mixed_case_to_lower_case(unpack_dir)


def _copy_unpacked_files(unpack_dir: Path, unpack_temp_dir_path: Path) -> None:
    """Copies unpacked files from the temporary directory to the final unpack directory.

    Treats every top-level directory (Installers, neutral, x86, x64, arm64, etc.) uniformly: each immediate child is a
    package directory. If it has a "Contents" subfolder, copy that; otherwise copy the package directory itself.

    """
    for top_level_dir in unpack_temp_dir_path.iterdir():
        if not top_level_dir.is_dir():
            continue

        for package_dir in top_level_dir.iterdir():
            if not package_dir.is_dir():
                continue

            # Relevant for VSIX packages
            content_dir = package_dir / "Contents"
            src = content_dir if content_dir.exists() else package_dir
            shutil.copytree(src, unpack_dir, dirs_exist_ok=True)


def is_mixed_case(text: str) -> bool:
    """Checks if a given text is mixed case.

    :param text: The text to check.

    :returns: True if the text is mixed case, False otherwise.

    """
    return not text.islower() and not text.isupper()


def _symlink_mixed_case_to_lower_case(unpack_dir: Path) -> None:
    """Creates symlinks for mixed-case directories to their lower-case equivalents.

    This is necessary because some tools may expect lower-case directory names, while others may use mixed-case names.

    :param unpack_dir: The path to the unpacked directory.

    """
    for file_path in unpack_dir.rglob("*"):
        if file_path.suffix.lower() not in {".h", ".hpp", ".hxx", ".inl"}:
            continue
        if is_mixed_case(file_path.name):
            lower_case_file_path = file_path.with_name(file_path.name.lower())
            if not lower_case_file_path.exists():
                lower_case_file_path.symlink_to(file_path.name)
