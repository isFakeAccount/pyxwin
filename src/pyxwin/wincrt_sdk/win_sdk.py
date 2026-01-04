"""Module for extracting Windows SDK packages from Pyxwin Packages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyxwin.core.pyxwin_exceptions import PyxwinError, PyxwinMissingPackageError, UnsupportedPackageConfigurationError
from pyxwin.wincrt_sdk.manifest_datatypes import Architecture, ManifestItem, ManifestOptions, ManifestPayload, PayloadType, SDKPayload

if TYPE_CHECKING:
    from packaging.version import Version

    from pyxwin.wincrt_sdk.manifest_datatypes import PyxwinPackages


def get_sdk_version(package_names: list[str], user_provided_sdk_version: str | None) -> tuple[str, Version]:
    """Parses the Windows SDK version from user input or fetches the latest available version from the package names.

    :param package_names: List of package names to parse.
    :param user_provided_sdk_version: User-provided SDK version string.

    :returns: A tuple containing the SDK package key and its Version object.

    :raises PyxwinError: If no valid SDK entries are found.

    """
    if user_provided_sdk_version:
        win_ver, version = ManifestOptions.parse_sdk_version(user_provided_sdk_version)
        sdk_key = f"Win{win_ver}SDK_{version}"
        return sdk_key, version

    parsed: list[tuple[int, Version]] = []

    for key in package_names:
        try:
            win_ver, version = ManifestOptions.parse_sdk_version(key)
        except PyxwinError:
            continue
        else:
            parsed.append((win_ver, version))

    if not parsed:
        raise PyxwinError("No valid Win*SDK_* entries found")

    win_ver, full_version = max(parsed)
    return f"Win{win_ver}SDK_{full_version}", full_version


def get_sdk_headers(
    manifest_options: ManifestOptions,
    sdk_key: str,
    sdk_version: Version,
    sdk_payloads: list[ManifestPayload],
) -> dict[str, SDKPayload]:
    """Gets the SDK header payloads."""
    header_payloads: dict[str, SDKPayload] = {}

    suffixes = (
        "Windows SDK Desktop Headers x86-x86_en-us.msi",
        "Windows SDK OnecoreUap Headers x86-x86_en-us.msi",
        "Windows SDK for Windows Store Apps Headers-x86_en-us.msi",
        "Windows SDK for Windows Store Apps Headers OnecoreUap-x86_en-us.msi",
    )

    for p in sdk_payloads:
        if p.file_name.endswith(suffixes):
            header_payloads[p.file_name] = SDKPayload.from_manifest_payload(
                manifest_payload=p,
                sdk_prefix=sdk_key,
                kind=PayloadType.SDK_HEADERS,
                target_arch=Architecture.ALL,
                sdk_version=sdk_version,
            )

    if len(header_payloads) != len(suffixes):
        raise PyxwinMissingPackageError("Not all SDK header payloads found in manifest.")

    for arch in manifest_options.arch:
        arch_str = arch.to_crt_package_id_str().lower()
        payload_id = f"Installers\\Windows SDK Desktop Headers {arch_str}-x86_en-us.msi"

        win_sdk_hdr_arch: ManifestPayload | None = next((p for p in sdk_payloads if p.file_name == payload_id), None)
        if win_sdk_hdr_arch is None:
            raise UnsupportedPackageConfigurationError(f"SDK header payload '{payload_id}' not found in manifest.")

        header_payloads[win_sdk_hdr_arch.file_name] = SDKPayload.from_manifest_payload(
            manifest_payload=win_sdk_hdr_arch,
            sdk_prefix=sdk_key,
            kind=PayloadType.SDK_HEADERS,
            target_arch=arch,
            sdk_version=sdk_version,
        )
    return header_payloads


def get_sdk_libs(
    packages_manifest: dict[str, list[ManifestItem]],
    manifest_options: ManifestOptions,
    sdk_key: str,
    sdk_version: Version,
    sdk_payloads: list[ManifestPayload],
) -> dict[str, SDKPayload]:
    """Gets the SDK library payloads."""
    lib_payloads: dict[str, SDKPayload] = {}

    for arch in manifest_options.arch:
        arch_str = arch.to_crt_package_id_str().lower()
        payload_id = f"Installers\\Windows SDK Desktop Libs {arch_str}-x86_en-us.msi"

        p = next((p for p in sdk_payloads if p.file_name == payload_id), None)
        if p is None:
            raise UnsupportedPackageConfigurationError(f"SDK header payload '{payload_id}' not found in manifest.")

        lib_payloads[p.file_name] = SDKPayload.from_manifest_payload(
            manifest_payload=p,
            sdk_prefix=sdk_key,
            kind=PayloadType.SDK_LIBS,
            target_arch=arch,
            sdk_version=sdk_version,
        )

    for sdk_payload in sdk_payloads:
        if sdk_payload.file_name.endswith("Windows SDK for Windows Store Apps Libs-x86_en-us.msi"):
            lib_payloads[sdk_payload.file_name] = SDKPayload.from_manifest_payload(
                manifest_payload=sdk_payload,
                sdk_prefix=sdk_key,
                kind=PayloadType.SDK_STORE_LIBS,
                target_arch=Architecture.ALL,
                sdk_version=sdk_version,
            )
            break
    else:
        raise PyxwinMissingPackageError("SDK Store Libs payload not found in manifest.")

    ucrt = packages_manifest.get("Microsoft.Windows.UniversalCRT.HeadersLibsSources.Msi")
    if ucrt is None:
        raise PyxwinError("Universal CRT package not found in manifest.")

    ucrt_payloads = ucrt[0].payloads
    if ucrt_payloads is None:
        raise PyxwinError("No payloads found for Universal CRT package.")

    for p in ucrt_payloads:
        if p.file_name == "Universal CRT Headers Libraries and Sources-x86_en-us.msi":
            lib_payloads[p.file_name] = SDKPayload.from_manifest_payload(
                manifest_payload=p,
                sdk_prefix=sdk_key,
                kind=PayloadType.UCRT,
                target_arch=Architecture.ALL,
                sdk_version=sdk_version,
            )
            break
    else:
        raise PyxwinError("Universal CRT MSI package not found in manifest.")

    return lib_payloads


def get_cab_files(
    sdk_key: str,
    sdk_version: Version,
    sdk_payloads: list[ManifestPayload],
    packages_manifest: dict[str, list[ManifestItem]],
) -> dict[str, SDKPayload]:
    """Gets all the CAB file payloads from the SDK payloads."""
    cab_payloads: dict[str, SDKPayload] = {}
    for p in sdk_payloads:
        if p.file_name.endswith(".cab"):
            cab_payloads[p.file_name] = SDKPayload.from_manifest_payload(
                manifest_payload=p,
                sdk_prefix=sdk_key,
                kind=PayloadType.CAB_FILE,
                target_arch=Architecture.ALL,
                sdk_version=sdk_version,
            )

    ucrt = packages_manifest.get("Microsoft.Windows.UniversalCRT.HeadersLibsSources.Msi")
    if ucrt is None:
        raise PyxwinError("Universal CRT package not found in manifest.")
    ucrt_payloads = ucrt[0].payloads
    if ucrt_payloads is None:
        raise PyxwinError("No payloads found for Universal CRT package.")

    for p in ucrt_payloads:
        if p.file_name.endswith(".cab"):
            cab_payloads[p.file_name] = SDKPayload.from_manifest_payload(
                manifest_payload=p,
                sdk_prefix=sdk_key,
                kind=PayloadType.CAB_FILE,
                target_arch=Architecture.ALL,
                sdk_version=sdk_version,
            )

    return cab_payloads


async def get_sdk(pyxwin_packages: PyxwinPackages, manifest_options: ManifestOptions) -> dict[str, SDKPayload]:
    """Gets the Windows SDK packages from the dict of all package manifests."""
    sdk_key, sdk_version = get_sdk_version(list(pyxwin_packages.keys()), manifest_options.sdk_version)

    win_sdk = pyxwin_packages[sdk_key][0]
    sdk_payloads = win_sdk.payloads
    if sdk_payloads is None:
        raise PyxwinError(f"No payloads found for SDK package '{sdk_key}'.")

    header_payloads = get_sdk_headers(
        manifest_options=manifest_options,
        sdk_key=sdk_key,
        sdk_version=sdk_version,
        sdk_payloads=sdk_payloads,
    )
    lib_payloads = get_sdk_libs(
        packages_manifest=pyxwin_packages,
        manifest_options=manifest_options,
        sdk_key=sdk_key,
        sdk_version=sdk_version,
        sdk_payloads=sdk_payloads,
    )
    cab_payloads = get_cab_files(
        sdk_key=sdk_key,
        sdk_version=sdk_version,
        sdk_payloads=sdk_payloads,
        packages_manifest=pyxwin_packages,
    )
    return header_payloads | lib_payloads | cab_payloads
