"""Holds the global CLI options and runtime configuration for pyxwin."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, TypedDict

import typer


class ManifestOptions(TypedDict):
    """Holds the runtime configuration for pyxwin."""

    manifest: Path | None
    manifest_version: int
    channel: str


manifest_options: ManifestOptions = {
    "manifest": None,
    "manifest_version": 17,
    "channel": "release",
}

accept_license_opt = Annotated[
    bool,
    typer.Option(
        envvar="PYXWIN_ACCEPT_LICENSE",
        help="Doesn't display the prompt to accept the license.",
    ),
]
manifest_opt = Annotated[
    Path | None,
    typer.Option(
        help="Specifies a VS manifest to use from a file, rather than downloading it from the Microsoft site.",
    ),
]

manifest_version_opt = Annotated[int, typer.Option(help="Specifies the version of the VS manifest to use.")]

channel_opt = Annotated[str, typer.Option(help="Specifies the VS channel to use.")]
