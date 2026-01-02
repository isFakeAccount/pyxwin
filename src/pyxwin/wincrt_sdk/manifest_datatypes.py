"""Holds the Visual Studio manifest configuration types and defaults."""

from __future__ import annotations

from enum import StrEnum

# Note: Pydantic needs this outside of TYPE_CHECKING block
from pathlib import Path
from typing import NewType, Self

# Note: Pydantic needs this outside of TYPE_CHECKING block
from packaging.version import Version  # noqa: TC002
from platformdirs import user_cache_path
from pydantic import BaseModel, Field
from typing_extensions import TypeAliasType

from pyxwin.core.pyxwin_exceptions import MalformedJsonError, PyxwinError

JSON_t = TypeAliasType("JSON_t", "dict[str, JSON_t] | list[JSON_t] | str | int | float | bool | None")  # pyright: ignore[reportInvalidTypeForm]


class Architecture(StrEnum):
    """Enumeration of supported system architectures."""

    X86 = "x86"
    X86_64 = "x86_64"
    AARCH = "aarch"
    AARCH64 = "aarch64"
    ALL = "all"  # used for headers

    def as_microsoft_names(self) -> str:
        """Converts the Architecture enum to its Microsoft name representation.

        :returns: The Architecture str as Microsoft names.

        """
        mapping = {
            Architecture.X86: "x86",
            Architecture.X86_64: "x64",
            Architecture.AARCH: "arm",
            Architecture.AARCH64: "arm64",
            Architecture.ALL: "all",
        }
        return mapping[self]

    def to_atl_package_id_str(self) -> str:
        """Convert this architecture to the identifier format used in ATL package IDs.

        This is due to Microsoft shenanigans, all ATL architectures are uppercase.

        :returns: The architecture string as used by ATL package identifiers.

        """
        return self.to_crt_package_id_str().upper()

    def to_crt_package_id_str(self) -> str:
        """Converts the Architecture enum to its CRT ID name representation.

        This is due to Microsoft shenanigans, only ARM64 is uppercase only in the CRT libs because reasons

        :returns: The Architecture str as they appear in CRT ID names.

        """
        if self == Architecture.AARCH64:
            return self.as_microsoft_names().upper()
        return self.as_microsoft_names()


class Variant(StrEnum):
    """Enumeration of supported Windows variants.

    :var DESKTOP: Standard Desktop variant.
    :var ONECORE: OneCore Desktop variant.
    :var STORE: Store variant is for UWP apps.
    :var ALL: When payload is common to all variants, such as headers.

    """

    DESKTOP = "Desktop"
    ONECORE = "OneCore"
    STORE = "Store"
    ALL = "All"

    def __str__(self) -> str:
        """Returns the Microsoft name for the variant.

        :returns: The Microsoft variant name.

        """
        mapping = {
            Variant.DESKTOP: "Desktop",
            Variant.ONECORE: "OneCore.Desktop",
            Variant.STORE: "Store",
            Variant.ALL: "All",
        }
        return mapping[self]

    @classmethod
    def get_all_variants(cls) -> list[Variant]:
        """Returns all specific variants excluding 'ALL'.

        :returns: List of specific variants.

        """
        return [enum for enum in cls if enum != Variant.ALL]

    def get_spectre_str(self) -> str:
        """Returns the spectre variant of the variant.

        :returns: The spectre variant string.

        """
        return f"{self}.spectre"


class Channel(StrEnum):
    """Enumeration of supported Visual Studio channels."""

    STABLE = "stable"
    PREVIEW = "pre"
    RELEASE = "release"
    INSIDERS = "insiders"


class ManifestOptions(BaseModel, validate_assignment=True):
    """Holds the runtime configuration for pyxwin."""

    channel_manifest_path: Path | None
    manifest_version: int
    channel: Channel
    arch: list[Architecture]
    variant: list[Variant]
    cache_dir: Path
    crt_version: str | None = Field(pattern=r"^\d+\.\d+\.\d+\.\d+$")
    sdk_version: str | None = Field(pattern=r"^Win\d+SDK_\d+\.\d+\.\d+$")
    include_atl: bool = False
    include_spectre: bool = False

    @classmethod
    def get_default_manifest_options(cls) -> Self:
        """Returns the default manifest options for pyxwin.

        :returns: The default manifest options.

        """
        return cls(
            channel_manifest_path=None,
            manifest_version=18,
            channel=Channel.STABLE,
            arch=[Architecture.X86_64],
            variant=[Variant.DESKTOP],
            cache_dir=user_cache_path("pyxwin", "pyxwin") / "msvcrt",
            crt_version=None,
            sdk_version=None,
            include_atl=False,
            include_spectre=False,
        )


class ManifestPayload(BaseModel):
    """Represents a payload in the Visual Studio manifest."""

    sha256: str
    size: int
    url: str
    file_name: str = Field(alias="fileName")


class ItemType(StrEnum):
    """Enumeration of types of Manifest Items."""

    # Unused.
    BOOTSTRAPPER = "Bootstrapper"
    # Unused.
    CHANNEL = "Channel"
    # Unused.
    CHANNELPRODUCT = "ChannelProduct"
    # A composite package, no contents itself. Unused.
    COMPONENT = "Component"
    # A single executable. Unused.
    EXE = "Exe"
    # Another kind of composite package without contents, and no localization. Unused.
    GROUP = "Group"
    # Top level manifest
    MANIFEST = "Manifest"
    # MSI installer
    MSI = "Msi"
    # Unused.
    MSU = "Msu"
    # Nuget package. Unused.
    NUPKG = "Nupkg"
    # Unused
    PRODUCT = "Product"
    # A glorified zip file
    VSIX = "Vsix"
    # Windows feature install/toggle. Unused.
    WINDOWSFEATURE = "WindowsFeature"
    # Unused.
    WORKLOAD = "Workload"
    # Plain zip file (ie not vsix). Unused.
    ZIP = "Zip"


class ManifestItem(BaseModel, extra="ignore"):
    """Represents an item in the Visual Studio manifest or Package manifest."""

    id: str
    version: str
    type: ItemType
    payloads: list[ManifestPayload] | None = Field(default=None)
    # Channel manifests only
    installer_version: str | None = Field(default=None, alias="installerVersion")
    # Installer manifests only
    chip: str | None = Field(default=None)
    dependencies: JSON_t | None = Field(default=None)
    install_sizes: dict[str, int] | None = Field(default=None, alias="installSizes")


class VisualStudioManifest(BaseModel, extra="ignore"):
    """Represents either a Visual Studio channel manifest or an installer manifest."""

    channel_items: list[ManifestItem] | None = Field(default=None, alias="channelItems")
    packages: list[ManifestItem] | None = Field(default=None)


PyxwinPackages = NewType("PyxwinPackages", dict[str, list[ManifestItem]])


class PayloadType(StrEnum):
    """Package Payload type."""

    ATL_HEADERS = "AtlHeaders"
    ATL_LIBS = "AtlLibs"
    CRT_HEADERS = "CrtHeaders"
    CRT_LIBS = "CrtLibs"
    SDK_HEADERS = "SdkHeaders"
    SDK_LIBS = "SdkLibs"
    SDK_STORE_LIBS = "SdkStoreLibs"
    UCRT = "Ucrt"
    VCR_DEBUG = "VcrDebug"
    CAB_FILE = "CabFile"


def detect_arch_from_id(item_id: str, kind: PayloadType) -> Architecture:
    """Detects the architecture from the manifest item ID and kind."""
    if Architecture.AARCH64.as_microsoft_names() in item_id.lower():
        arch = Architecture.AARCH64
    elif Architecture.AARCH.as_microsoft_names() in item_id.lower():
        arch = Architecture.AARCH
    elif Architecture.X86_64.as_microsoft_names() in item_id.lower():
        arch = Architecture.X86_64
    elif Architecture.X86.as_microsoft_names() in item_id.lower():
        arch = Architecture.X86
    elif kind in (PayloadType.ATL_HEADERS, PayloadType.CRT_HEADERS, PayloadType.SDK_HEADERS):
        arch = Architecture.ALL
    else:
        raise PyxwinError("Unreachable: Manifest item does not specify a known architecture.")
    return arch


class CRTPayload(BaseModel):
    """Represents a CRT payload with its associated metadata.

    :var filename: The suggested filename for the payload when stored on disk.
    :var sha256: The sha-256 checksum of the payload.
    :var url: The url from which to acquire the payload.
    :var size: The total size of the payload.
    :var kind: The kind of the payload.
    :var target_arch: Specific architecture this payload targets.
    :var variant: Specific variant this payload targets.
    :var version: The version of the CRT.
    :var spectre_hardened: Indicates if the CRT payload is built with Spectre mitigations.
    :var install_size: The size the payload will take up when installed.

    """

    filename: str
    kind: PayloadType
    sha256: str
    size: int
    target_arch: Architecture
    url: str
    variant: Variant
    version: str
    spectre_hardened: bool
    # If a package has a single payload, this will be set to the actual
    # size it will be on disk when decompressed
    install_size: int | None

    @property
    def suggested_install_filepath(self) -> Path:
        """Returns the recommended install path w.r.t to pyxwin cache directory."""
        return Path(f"CRT_{self.version}", self.filename)

    @classmethod
    def from_manifest_item(cls, manifest_item: ManifestItem, kind: PayloadType, crt_version: Version, spectre_hardened: bool) -> Self:
        """Converts a ManifestItem to a CRTPayload of the specified kind.

        :param manifest_item: The ManifestItem to convert.
        :param kind: The type of payload to extract.
        :param crt_version: The version of the CRT this payload belongs to.
        :param spectre_hardened: Sets the `spectre_hardened` flag.

        :returns: The corresponding CRTPayload.

        :raises PyxwinError: If something goes wrong when determining the type of payload.

        """
        # The explicit conversions to str is needed for microsoft naming conventions.
        # See Variant.__str__()
        # ATL libs do not have Desktop/OneCore/Store variants, only Spectre or Non-Spectre.
        # Headers are applicable to all variants.
        if kind in (PayloadType.ATL_LIBS, PayloadType.ATL_HEADERS, PayloadType.CRT_HEADERS, PayloadType.SDK_HEADERS):
            variant = Variant.ALL
        # Onecore is variants of desktop so it is important to check those first.
        elif str(Variant.ONECORE) in manifest_item.id:
            variant = Variant.ONECORE
        elif str(Variant.DESKTOP) in manifest_item.id:
            variant = Variant.DESKTOP
        elif str(Variant.STORE) in manifest_item.id:
            variant = Variant.STORE
        else:
            raise PyxwinError("Unreachable: Manifest item does not specify a known variant.")

        arch = detect_arch_from_id(manifest_item.id, kind)

        if not manifest_item.payloads or len(manifest_item.payloads) == 0:
            raise MalformedJsonError(f"No payloads found for manifest item {manifest_item.id}.")

        install_size = manifest_item.install_sizes.get("targetDrive") if manifest_item.install_sizes is not None else None
        return cls(
            filename=manifest_item.payloads[0].file_name,
            kind=kind,
            sha256=manifest_item.payloads[0].sha256,
            size=manifest_item.payloads[0].size,
            target_arch=arch,
            url=manifest_item.payloads[0].url,
            variant=variant,
            version=str(crt_version),
            spectre_hardened=spectre_hardened,
            install_size=install_size,
        )


class SDKPayload(BaseModel):
    """Represents a SDK payload with its associated metadata.

    :var filename: The suggested filename for the payload when stored on disk.
    :var sha256: The sha-256 checksum of the payload.
    :var url: The url from which to acquire the payload.
    :var size: The total size of the payload.
    :var kind: The kind of the payload.
    :var target_arch: Specific architecture this payload targets.
    :var version: The version of the SDK.
    :var install_size: The size the payload will take up when installed.

    """

    filename: str
    kind: PayloadType
    sha256: str
    size: int
    target_arch: Architecture
    url: str
    version: str
    # If a package has a single payload, this will be set to the actual
    # size it will be on disk when decompressed
    install_size: int | None

    @property
    def suggested_install_filepath(self) -> Path:
        """Returns the recommended install path w.r.t to pyxwin cache directory."""
        return Path(f"SDK_{self.version}", self.filename)

    @classmethod
    def from_manifest_payload(
        cls,
        manifest_payload: ManifestPayload,
        sdk_prefix: str,
        kind: PayloadType,
        target_arch: Architecture,
        sdk_version: Version,
    ) -> Self:
        """Creates a SDKPayload from a ManifestPayload.

        :param manifest_payload: The ManifestPayload to convert.
        :param kind: The type of payload.
        :param target_arch: The target architecture of the payload.
        :param variant: The variant of the payload.

        :returns: The corresponding SDKPayload.

        """
        new_file_name = manifest_payload.file_name.replace(" ", "_").replace("\\", "_").lower()

        if kind == PayloadType.CAB_FILE:
            new_file_name = new_file_name.replace("installers_", "")

        return cls(
            filename=f"{sdk_prefix}_{new_file_name}" if kind != PayloadType.CAB_FILE else new_file_name,
            kind=kind,
            sha256=manifest_payload.sha256,
            size=manifest_payload.size,
            target_arch=target_arch,
            url=manifest_payload.url,
            version=str(sdk_version),
            install_size=None,
        )
