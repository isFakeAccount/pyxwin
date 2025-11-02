"""Entry point for the pyxwin command-line interface."""

from __future__ import annotations

import typer

from pyxwin.config import accept_license_opt, channel_opt, manifest_opt, manifest_options, manifest_version_opt

app = typer.Typer()


@app.callback()
def app_callback(
    accept_license: accept_license_opt = False,
    manifest: manifest_opt = manifest_options["manifest"],
    manifest_version: manifest_version_opt = manifest_options["manifest_version"],
    channel: channel_opt = manifest_options["channel"],
) -> None:
    """Callback function for the pyxwin CLI. Processes the global CLI options."""
    if accept_license:
        print("Microsoft Software License Terms accepted.")
    else:
        accept = input(
            "Do you accept the Microsoft Software License Terms at "
            "(https://codeberg.org/YoshikageKira/pyxwin/src/branch/master/LICENSES/LICENSE-Microsoft-Build-Tools.md)? (y/n): "
        )
        if accept.lower() != "y":
            print("You must accept the license to proceed.")
            raise typer.Exit(code=1)

        print("Microsoft Software License Terms accepted.")

    manifest_options["manifest"] = manifest
    manifest_options["manifest_version"] = manifest_version
    manifest_options["channel"] = channel


def main() -> None:
    """Entry point for the pyxwin CLI."""
    app()


if __name__ == "__main__":
    main()
