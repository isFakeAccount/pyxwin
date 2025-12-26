"""Module for HTTP client functionality."""

from __future__ import annotations

import httpx

from pyxwin.core.pyxwin_exceptions import PyxwinDownloadError


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


async def fetch_file_bytes(url: str) -> bytes:
    """Fetches file from the given URL and returns the content in bytes.

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
        return response.content
