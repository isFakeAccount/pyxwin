"""Module to provide async functions for reading and writing files."""

from __future__ import annotations

import asyncio
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles

from pyxwin.core.https_client import fetch_file_bytes
from pyxwin.core.pyxwin_exceptions import PyxwinDownloadError

if TYPE_CHECKING:
    from pathlib import Path


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


async def async_write_bytes(path: Path, raw_bytes: bytes) -> None:
    """Asynchronously write bytes to a file.

    This function behaves similarly to :meth:`pathlib.Path.write_bytes`, but performs the operation asynchronously using
    :mod:`aiofiles`.

    :param path: The path to the file where text will be written.
    :param raw_bytes: The bytes content to write.

    :returns: None

    :raises OSError: If there is an error opening or writing to the file.

    """
    async with aiofiles.open(path, "wb") as fp:
        await fp.write(raw_bytes)


async def download_and_validate(url: str, file_path: Path, target_sha256: str) -> None:
    """Downloads the file from the specified URL and validates its SHA256 checksum.

    :param url: The URL to download the file from.
    :param file_path: The path to save the downloaded file.
    :param target_sha256: The expected SHA256 checksum of the file.

    :raises PyxwinDownloadError: If the downloaded file's SHA256 does not match the expected value.
    :raises OSError: If there is an error writing the file to disk.

    """
    raw_bytes = await fetch_file_bytes(url)

    downloaded_sha = sha256(raw_bytes).hexdigest()
    if target_sha256.lower() != downloaded_sha.lower():
        raise PyxwinDownloadError(status_code=None, message=f"SHA256 mismatch for url {url}")

    await async_write_bytes(file_path, raw_bytes)


async def multi_download_and_validate(files: list[tuple[str, Path, str]]) -> None:
    """Downloads and validates multiple files concurrently.

    :param files: A list of tuples containing (url, file_path, target_sha256) for each file.

    """
    async with asyncio.TaskGroup() as group:
        for url, file_path, target_sha256 in files:
            group.create_task(download_and_validate(url, file_path, target_sha256))
