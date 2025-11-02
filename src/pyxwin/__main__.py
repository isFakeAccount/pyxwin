"""Entry point for the pyxwin command-line interface."""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer()


@app.command()
def printname(name: str) -> None:
    print(name)


@app.command()
def printname2(*, name: str = typer.Option("World", "--name", "-n")) -> None:
    print(name)


@app.callback()
def app_callback(
    accept_license: Annotated[
        bool,
        typer.Option(envvar="PYXWIN_ACCEPT_LICENSE", help="Doesn't display the prompt to accept the license."),
    ] = False,
    manifest: Annotated[
        str | None,
        typer.Option(
            None,
            "--manifest",
            help="Specifies a VS manifest to use from a file, rather than downloading it from the Microsoft site",
        ),
    ] = None,
    manifest_version: Annotated[
        int,
        typer.Option("--manifest-version", help="The manifest version to retrieve", show_default=True),
    ] = 17,
    channel: Annotated[
        str,
        typer.Option("--channel", help="The product channel to use", show_default=True),
    ] = "release",
    sdk_version: Annotated[
        str | None,
        typer.Option(
            None,
            "--sdk-version",
            help=(
                "If specified, this is the version of the SDK that the user wishes to use instead of"
                " defaulting to the latest SDK available in the manifest"
            ),
        ),
    ] = None,
    crt_version: Annotated[
        str | None,
        typer.Option(
            None,
            "--crt-version",
            help=(
                "If specified, this is the version of the MSVCRT that the user wishes to use instead of"
                " defaulting to the latest MSVCRT available in the manifest"
            ),
        ),
    ] = None,
    include_atl: Annotated[
        bool,
        typer.Option(
            False,
            "--include-atl",
            help="Whether to include the Active Template Library (ATL) in the installation",
        ),
    ] = False,
    include_debug_runtime: Annotated[
        bool,
        typer.Option(
            False,
            "--include-debug-runtime",
            help="Whether to include VCR debug libraries",
        ),
    ] = False,
) -> None:
    """Callback function for the pyxwin CLI.

    Global CLI options accepted here include manifest selection, versions, channels, and
    flags to include optional components during installation.
    """
    # License acceptance handling
    if accept_license:
        print("Microsoft Software License Terms accepted.")
    else:
        accept = input("Do you accept the Microsoft Software License Terms? (y/n): ")
        if accept.lower() != "y":
            print("You must accept the license to proceed.")
            raise typer.Exit(code=1)

        print("Microsoft Software License Terms accepted.")

    # Echo out the selected options at startup for clarity (could be removed later)
    # Only show non-default or specified values to avoid noisy output
    if manifest is not None:
        print(f"Using manifest file: {manifest}")
    print(f"Manifest version: {manifest_version}")
    print(f"Channel: {channel}")
    if sdk_version is not None:
        print(f"Requested SDK version: {sdk_version}")
    if crt_version is not None:
        print(f"Requested CRT version: {crt_version}")
    if include_atl:
        print("ATL will be included in the installation.")
    if include_debug_runtime:
        print("VCR debug libraries will be included in the installation.")


def main() -> None:
    """Entry point for the pyxwin CLI."""
    app()


if __name__ == "__main__":
    main()
