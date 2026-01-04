"""Module for extracting Windows CRT packages from Pyxwin Packages."""

from __future__ import annotations

from itertools import product
from typing import TYPE_CHECKING, Any, cast

from packaging.version import Version

from pyxwin.core.pyxwin_exceptions import UnsupportedPackageConfigurationError
from pyxwin.wincrt_sdk.manifest_datatypes import (
    CRTPayload,
    ManifestOptions,
    PayloadType,
    PyxwinPackages,
    Variant,
)

if TYPE_CHECKING:
    from pyxwin.wincrt_sdk.manifest_datatypes import ManifestOptions


def extract_version(component_id: str) -> str | None:
    """Extracts a version number (e.g., '14.32.17.2') from a Visual Studio component ID.

    The function looks for four consecutive numeric segments separated by dots within the given component ID (e.g.,
    'Microsoft.VisualStudio.Component.VC.14.32.17.2.x86.x64'). If no such pattern exists, it returns None.

    :param component_id: The full component identifier string.

    :returns: The extracted version string if found, otherwise None.

    """
    parts = component_id.split(".")
    for i in range(len(parts) - 3):
        if all(p.isdigit() for p in parts[i : i + 4]):
            return ".".join(parts[i : i + 4])
    return None


def grab_payload_from_pyxwin_packages(
    pyxwin_packages: PyxwinPackages,
    item_id: str,
    kind: PayloadType,
    crt_version: Version,
    spectre_hardened: bool,
) -> CRTPayload:
    """Helper function to grab the correct library from packages manifest.

    :param packages_manifest: The full packages manifest.
    :param crt_lib_id: The ID of the CRT library to fetch.
    :param kind: The type of payload being requested.

    :returns: The CRTPayload for the specified CRT library.

    """
    try:
        return CRTPayload.from_manifest_item(
            pyxwin_packages[item_id][0],
            kind,
            crt_version,
            spectre_hardened,
        )
    except KeyError as key_error:
        raise UnsupportedPackageConfigurationError(f"CRT header / library package '{item_id}' may not be available.") from key_error


async def get_toolchain_artifact(
    pyxwin_packages: PyxwinPackages,
    manifest_options: ManifestOptions,
    artifact_type: PayloadType,
) -> dict[str, CRTPayload]:
    """Gets the Windows CRT packages from the dict of all package manifests."""
    # There is only one payload for the build tools.
    build_tools = pyxwin_packages["Microsoft.VisualStudio.Product.BuildTools"][0]
    build_dependencies = cast("dict[str, Any]", build_tools.dependencies)  # pyright: ignore[reportUnknownMemberType]

    # Goal here is to get list of all CRT versions.
    # Architecture doesn't mean anything here. Could be anything (x86/x64/arm/arm64).
    crt_version_rs_versions = [
        Version(ver)  # Force multiline
        for key in build_dependencies  # Force multiline
        if key.endswith(".x86.x64")  # Force multiline
        and (ver := extract_version(key)) is not None  # Force multiline
    ]

    # Use the specified CRT version
    if manifest_options.crt_version is not None:
        crt_version = Version(manifest_options.crt_version)
        if crt_version not in crt_version_rs_versions:
            raise UnsupportedPackageConfigurationError(f"Specified CRT version '{crt_version}' is not available.")
    else:
        # otherwise use the latest available.
        crt_version = max(crt_version_rs_versions)

    header_id = f"Microsoft.VC.{crt_version}.CRT.Headers.base" if artifact_type == PayloadType.CRT_LIBS else f"Microsoft.VC.{crt_version}.ATL.Headers.base"
    pruned_crt_packages = {
        header_id: grab_payload_from_pyxwin_packages(
            pyxwin_packages=pyxwin_packages,
            item_id=header_id,
            kind=PayloadType.CRT_HEADERS if artifact_type == PayloadType.CRT_LIBS else PayloadType.ATL_HEADERS,
            crt_version=crt_version,
            spectre_hardened=False,
        )
    }
    if artifact_type == PayloadType.CRT_LIBS:
        pruned_crt_packages.update(_get_crt_libs(pyxwin_packages, manifest_options, crt_version))
    else:
        pruned_crt_packages.update(_get_atl_libs(pyxwin_packages, manifest_options, crt_version))

    return pruned_crt_packages


def _get_atl_libs(
    pyxwin_packages: PyxwinPackages,
    manifest_options: ManifestOptions,
    crt_version: Version,
) -> dict[str, CRTPayload]:
    """Internal helper to get ATL libraries."""
    pruned_atl_libraries: dict[str, CRTPayload] = {}

    for arch in manifest_options.arch:
        # Microsoft shenanigans: ATL arch is all uppercase.
        arch_str = arch.to_atl_package_id_str()
        # ATL doesn't have the Desktop/OneCore/Store distinction, only non-spectre and spectre matter here
        atl_lib_id = f"Microsoft.VC.{crt_version}.ATL.{arch_str}.base"

        pruned_atl_libraries[atl_lib_id] = grab_payload_from_pyxwin_packages(
            pyxwin_packages=pyxwin_packages,
            item_id=atl_lib_id,
            kind=PayloadType.ATL_LIBS,
            crt_version=crt_version,
            spectre_hardened=False,
        )

        if not manifest_options.include_spectre:
            continue

        atl_lib_id = f"Microsoft.VC.{crt_version}.ATL.{arch_str}.Spectre.base"
        pruned_atl_libraries[atl_lib_id] = grab_payload_from_pyxwin_packages(
            pyxwin_packages=pyxwin_packages,
            item_id=atl_lib_id,
            kind=PayloadType.ATL_LIBS,
            crt_version=crt_version,
            spectre_hardened=True,
        )

    return pruned_atl_libraries


def _get_crt_libs(
    pyxwin_packages: PyxwinPackages,
    manifest_options: ManifestOptions,
    crt_version: Version,
) -> dict[str, CRTPayload]:
    """Internal helper to get CRT libraries."""
    pruned_crt_libraries: dict[str, CRTPayload] = {}
    # First, add all non-spectre libraries

    # Replace 'ALL' with all specific variants
    manifest_options_variant = Variant.get_all_variants() if manifest_options.variant == [Variant.ALL] else manifest_options.variant

    for arch, variant in product(manifest_options.arch, manifest_options_variant):
        arch_str = arch.to_crt_package_id_str()
        crt_lib_id = f"Microsoft.VC.{crt_version}.CRT.{arch_str}.{variant}.base"
        pruned_crt_libraries[crt_lib_id] = grab_payload_from_pyxwin_packages(
            pyxwin_packages=pyxwin_packages,
            item_id=crt_lib_id,
            kind=PayloadType.CRT_LIBS,
            crt_version=crt_version,
            spectre_hardened=False,
        )

        # Only Desktop and OneCore variants have spectre-hardened versions
        if not manifest_options.include_spectre or variant == Variant.STORE:
            continue

        crt_lib_id = f"Microsoft.VC.{crt_version}.CRT.{arch_str}.{variant}.spectre.base"
        pruned_crt_libraries[crt_lib_id] = grab_payload_from_pyxwin_packages(
            pyxwin_packages=pyxwin_packages,
            item_id=crt_lib_id,
            kind=PayloadType.CRT_LIBS,
            crt_version=crt_version,
            spectre_hardened=True,
        )

    return pruned_crt_libraries
