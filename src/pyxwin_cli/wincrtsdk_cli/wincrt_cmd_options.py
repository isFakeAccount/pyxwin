"""Command-line options for the `pyxwin wincrt` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pyxwin.wincrt_sdk.manifest_datatypes import Channel, ManifestVersion

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
        dir_okay=False,
        file_okay=True,
        resolve_path=True,
        readable=True,
    ),
]

cache_dir_opt = Annotated[
    Path,
    typer.Option(
        help="Specifies a custom cache directory for pyxwin to use, rather than the default platform-specific cache directory.",
        dir_okay=True,
        file_okay=False,
        resolve_path=True,
    ),
]

manifest_version_opt = Annotated[ManifestVersion, typer.Option(help="Specifies the version of the VS manifest to use.")]

channel_opt = Annotated[Channel, typer.Option(help="Specifies the VS channel to use.")]

workloads_opt = Annotated[
    list[str],
    typer.Option(
        help="Specifies the Visual Studio workloads to install. Can be specified multiple times for multiple workloads.",
    ),
]
