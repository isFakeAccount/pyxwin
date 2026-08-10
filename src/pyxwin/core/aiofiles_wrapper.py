"""Module to provide async functions for reading and writing files."""

from __future__ import annotations

import asyncio
from hashlib import new, sha256
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
import httpx

from pyxwin.core.pyxwin_exceptions import PyxwinDownloadError

if TYPE_CHECKING:
    from pathlib import Path

    from rich.progress import Progress


async def fetch_file(url: str) -> str:
    """Fetches file from the given URL and returns the content in text.

    :param url: The URL of the file to fetch.

    :returns: The content of the fetched file as text.

    :raises PyxwinDownloadError: If the HTTP request fails.

    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            raise PyxwinDownloadError(status_code=response.status_code, message=str(http_err)) from http_err
        return response.text


async def async_read_text(path: Path, encoding: str = "utf-8") -> str:
    """Asynchronously read text data from a file.

    This function behaves similarly to :meth:`pathlib.Path.read_text`, but performs the operation asynchronously using
    :mod:`aiofiles`.

    :param path: The path to the file to read.
    :param encoding: The text encoding to use (default is "utf-8").

    :returns: The contents of the file as a string.

    :raises OSError: If there is an error opening or reading the file.

    """
    async with aiofiles.open(path, encoding=encoding) as fp:
        return await fp.read()


async def hash_file(path: Path, algorithm: str = "sha256", chunk_size: int = 1024 * 1024) -> str:
    """Computes the hex digest of a file's contents asynchronously, reading in chunks.

    :param path: Path to the file to hash.
    :param algorithm: Hash algorithm name (e.g. "sha256", "md5", "sha1").
    :param chunk_size: Number of bytes to read per chunk (default 1 MB).

    :returns: The hex digest string.

    """
    hasher = new(algorithm)
    async with aiofiles.open(path, "rb") as f:
        while chunk := await f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


async def async_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Asynchronously write text data to a file.

    This function behaves similarly to :meth:`pathlib.Path.write_text`, but performs the operation asynchronously using
    :mod:`aiofiles`.

    :param path: The path to the file where text will be written.
    :param text: The text content to write.
    :param encoding: The text encoding to use (default is "utf-8").

    :returns: None

    :raises OSError: If there is an error opening or writing to the file.

    """
    async with aiofiles.open(path, "w", encoding=encoding) as fp:
        await fp.write(text)


async def fetch_file_bytes(url: str) -> bytes:
    """Fetches file from the given URL and returns the content in bytes.

    :param url: The URL of the file to fetch.

    :returns: The content of the fetched file as bytes.

    :raises PyxwinDownloadError: If the HTTP request fails.

    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, follow_redirects=True)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            raise PyxwinDownloadError(status_code=response.status_code, message=str(http_err)) from http_err
        return response.content


async def stream_download_and_hash(url: str, file_path: Path, target_sha256: str, semaphore: asyncio.Semaphore, progress: Progress | None) -> None:
    """Streams a file from URL to disk while computing its SHA256 incrementally.

    :param url: The URL to download the file from.
    :param file_path: The path to save the downloaded file.
    :param target_sha256: The expected SHA256 checksum of the downloaded file.
    :param semaphore: The semaphore to limit concurrent downloads.
    :param progress: The progress tracker for the download process.

    :raises PyxwinDownloadError: If the HTTP request fails.
    :raises OSError: If there is an error writing the file to disk.

    """
    hasher = sha256()

    async with semaphore:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as http_err:
                raise PyxwinDownloadError(status_code=response.status_code, message=str(http_err)) from http_err

            total = int(response.headers.get("content-length", 0))
            task_id = None
            if progress is not None:
                task_id = progress.add_task(f"Downloading {file_path.name}...", total=total)

            async with aiofiles.open(file_path, "wb") as fp:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    hasher.update(chunk)
                    await fp.write(chunk)

                    if progress is not None and task_id is not None:
                        progress.update(task_id, advance=len(chunk))
            progress.remove_task(task_id) if progress is not None and task_id is not None else None

        if target_sha256.lower() != hasher.hexdigest().lower():
            raise PyxwinDownloadError(status_code=None, message=f"SHA256 mismatch for url {url}")


async def multi_download_and_validate(files: list[tuple[str, Path, str]], *, max_concurrent: int = 5, progress: Progress | None = None) -> None:
    """Downloads and validates multiple files concurrently.

    :param files: A list of tuples containing (url, file_path, target_sha256) for each file.
    :param max_concurrent: The maximum number of concurrent downloads (default is 5).
    :param progress: The progress tracker for the download process.

    """
    semaphore = asyncio.Semaphore(max_concurrent)
    task_groups: list[asyncio.Task[None]] = []
    async with asyncio.TaskGroup() as group:
        for url, file_path, target_sha256 in files:
            task_groups.append(group.create_task(stream_download_and_hash(url, file_path, target_sha256, semaphore, progress)))

        total_task_id = progress.add_task("Total Progress", total=len(files)) if progress is not None else None
        for task in task_groups:
            await task
            if progress is not None and total_task_id is not None:
                progress.update(total_task_id, advance=1)
