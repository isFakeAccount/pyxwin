"""Module to provide async functions for reading and writing files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import aiofiles

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
