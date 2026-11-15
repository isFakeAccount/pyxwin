"""Downloads and extracts Windows Python builds from github.com/isFakeAccount/windows-python-builds."""

from __future__ import annotations

import asyncio
import functools
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import TypeAdapter

from pyxwin.core.aiofiles_wrapper import DownloadItem, multi_download_and_validate
from pyxwin.python_sdk.github_datatypes import ReleaseList

if TYPE_CHECKING:
    from rich.progress import Progress, TaskID

    from pyxwin.python_sdk.github_datatypes import Release, ReleaseAsset


async def fetch_releases() -> dict[str, Release]:
    """Lists the latest 30 releases from Github repo."""
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.github.com/repos/isFakeAccount/windows-python-builds/releases")

    gh_releases = TypeAdapter(ReleaseList).validate_json(resp.read())

    release_data: dict[str, Release] = {}
    for release in gh_releases.root:
        if release.name is None:
            continue
        release_data[release.name.lower()] = release

    return release_data


async def download_python_builds(
    pyxwin_cache_dir: Path, release_name: str, python_release_assets: list[ReleaseAsset], progress: Progress | None = None
) -> None:
    """Downloads the python builds from the specified release.

    :param pyxwin_cache_dir: Directory in which the Python SDK files will be downloaded.
    :param release_name: Release to download.
    :param python_release_assets: Python release assets to download.

    """
    download_dir = pyxwin_cache_dir / "pysdk" / "downloads" / release_name
    download_dir.mkdir(parents=True, exist_ok=True)

    files_to_download: list[DownloadItem] = []

    for python_release_asset in python_release_assets:
        _download_path = download_dir / python_release_asset.name
        if not _download_path.exists():
            files_to_download.append(
                DownloadItem(
                    str(python_release_asset.browser_download_url),
                    download_dir / python_release_asset.name,
                    python_release_asset.digest.removeprefix("sha256:") if python_release_asset.digest else "",
                )
            )

    async with asyncio.TaskGroup() as tg:
        tg.create_task(multi_download_and_validate(files_to_download, max_concurrent=5, progress=progress))


async def unpack_python_builds(pyxwin_cache_dir: Path, release_name: str, python_builds: list[str], progress: Progress | None = None) -> None:
    """Unpacks the downloaded python builds.

    :param pyxwin_cache_dir: Directory in which the Python SDK files will be downloaded.
    :param release_name: Release to unpack.
    :param python_builds: Python builds to unpack.

    """
    download_dir = pyxwin_cache_dir / "pysdk" / "downloads" / release_name
    unpack_dir = pyxwin_cache_dir / "pysdk" / "unpacked" / release_name
    unpack_dir.mkdir(parents=True, exist_ok=True)

    wanted = {build.lower() for build in python_builds}

    progress_task: TaskID | None = None
    if progress is not None:
        progress_task = progress.add_task(description="Unpacking Python builds...", total=len(wanted))

    async with asyncio.TaskGroup() as tg:
        for downloaded_file in download_dir.iterdir():
            if downloaded_file.name.lower() in wanted:
                task = tg.create_task(
                    asyncio.to_thread(
                        _unpack_flat,
                        downloaded_file,
                        unpack_dir / downloaded_file.stem.removesuffix(".tar"),
                    )
                )
                if progress is not None and progress_task is not None:
                    task.add_done_callback(functools.partial(_task_progress_update_callback, progress=progress, progress_task=progress_task))


def _task_progress_update_callback(_: asyncio.Task[None], progress: Progress, progress_task: TaskID) -> None:
    progress.update(progress_task, advance=1)


def _unpack_flat(archive: Path, destination: Path) -> None:
    """Extract archive, dropping a single top-level folder if there is one."""
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        shutil.unpack_archive(str(archive), tmp)
        entries = list(Path(tmp).iterdir())
        root = entries[0] if len(entries) == 1 and entries[0].is_dir() else Path(tmp)
        for child in root.iterdir():
            shutil.move(str(child), str(destination / child.name))
