"""Defines exceptions for the pyxwin package."""

from __future__ import annotations


class PyxwinError(Exception):
    """Base exception class for pyxwin errors."""


class PyxwinDownloadError(PyxwinError):
    """Raised when a download operation fails."""

    def __init__(self, status_code: int | None = None, message: str | None = None) -> None:
        """Initializes the PyxwinDownloadError."""
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class MalformedJsonError(PyxwinError):
    """Raised when a JSON file is malformed or cannot be parsed."""


class InvalidInputDataError(PyxwinError):
    """Raised when the input data is invalid or malformed."""
