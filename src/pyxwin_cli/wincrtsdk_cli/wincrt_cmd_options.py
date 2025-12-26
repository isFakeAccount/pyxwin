"""Command-line options for the `pyxwin wincrt` command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from pyxwin.wincrt_sdk.manifest_datatypes import Architecture, Channel, Variant

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

manifest_version_opt = Annotated[int, typer.Option(help="Specifies the version of the VS manifest to use.")]

channel_opt = Annotated[Channel, typer.Option(help="Specifies the VS channel to use.")]

arch_opt = Annotated[
    list[Architecture],
    typer.Option(
        "--arch",
        "-a",
        help="Specifies the system architecture to use when downloading build tools. Can be specified multiple times for multiple architectures.",
    ),
]

variant_opt = Annotated[
    list[Variant],
    typer.Option(
        "--variant",
        "-v",
        help="Specifies the Windows variant to target when downloading build tools. Can be specified multiple times for multiple variants.",
    ),
]

crt_version_opt = Annotated[
    str | None,
    typer.Option(
        help="Specifies the version of the Windows CRT to download (e.g., '14.44.17.14'). If not specified, the latest version will be used.",
    ),
]

sdk_version_opt = Annotated[
    str | None,
    typer.Option(
        help="Specifies the version of the Windows SDK to download (e.g., '10.0.26100'). If not specified, the latest version will be used.",
    ),
]

include_atl_opt = Annotated[
    bool,
    typer.Option(
        help="Includes the Active Template Library (ATL) in the installation libraries when downloading the Windows CRT.",
    ),
]

include_spectre_opt = Annotated[
    bool,
    typer.Option(
        help="Includes the Spectre variant in the installation libraries when downloading the Windows CRT.",
    ),
]
