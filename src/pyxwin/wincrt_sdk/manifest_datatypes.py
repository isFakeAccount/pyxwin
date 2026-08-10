"""Holds the Visual Studio manifest configuration types and defaults."""

from __future__ import annotations

from enum import IntEnum, StrEnum
from pathlib import Path, PureWindowsPath
from typing import Any, Self

from platformdirs import user_cache_path
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ManifestPayload(BaseModel):
    """Represents a payload in the Visual Studio channel or installer manifest."""

    model_config = ConfigDict(frozen=True)

    sha256: str
    size: int
    url: str
    file_name: str = Field(alias="fileName")

    def suggested_install_filepath(self, parent_directory: Path | None) -> Path:
        """Returns the suggested install path.

        :param parent_directory: Returns the suggested install path within this directory.

        :returns: Suggested install path.

        """
        install_location = Path(PureWindowsPath(self.file_name))

        if parent_directory is not None:
            return parent_directory / install_location

        return install_location


class ItemType(StrEnum):
    """Enumeration of types of channel / package items."""

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
    # Workload is set of packages needed for a specific development scenario.
    WORKLOAD = "Workload"
    # Plain zip file (ie not vsix). Unused.
    ZIP = "Zip"


class Architecture(StrEnum):
    """Enumeration of supported system architectures."""

    X86 = "x86"
    X86_64 = "x64"
    ARM = "arm"
    ARM64 = "arm64"
    NEUTRAL = "neutral"

    @classmethod
    def _missing_(cls, value: object) -> Self | None:
        if not isinstance(value, str):
            return None

        value = value.lower()
        for member in cls:
            if member.value == value:
                return member
        return None


class VisualStudioChannelManifestItem(BaseModel, extra="ignore", populate_by_name=True):
    """Represents a channel item from Visual Studio channel manifest."""

    id: str
    version: str
    type: ItemType
    payloads: list[ManifestPayload] | None = Field(default=None)
    chip: Architecture | None = Field(default=None, validation_alias=AliasChoices("chip"))
    product_arch: Architecture | None = Field(default=None, alias="productArch")


class VisualStudioChannelManifest(BaseModel, extra="ignore"):
    """Represents either a Visual Studio channel manifest or an installer manifest."""

    channel_items: list[VisualStudioChannelManifestItem] | None = Field(default=None, alias="channelItems")


class VisualStudioInstallerPackage(BaseModel, extra="ignore", populate_by_name=True):
    """Represents a package from the Visual Studio Installer Manifest."""

    id: str
    version: str
    type: ItemType
    payloads: list[ManifestPayload] | None = Field(default=None)
    chip: Architecture | None = Field(default=None, validation_alias=AliasChoices("chip", "machineArch"))
    product_arch: Architecture | None = Field(default=None, alias="productArch")
    dependencies: dict[str, Any] | None = Field(default=None)
    install_sizes: dict[str, int] | None = Field(default=None, alias="installSizes")


class VisualStudioInstallerManifest(BaseModel, extra="ignore"):
    """Represents either a Visual Studio channel manifest or an installer manifest."""

    packages: list[VisualStudioInstallerPackage] | None = Field(default=None)


PyxwinPackages = dict[str, dict[Architecture, VisualStudioInstallerPackage]]


class Channel(StrEnum):
    """Enumeration of supported Visual Studio channels."""

    INSIDERS = "insiders"
    PREVIEW = "pre"
    RELEASE = "release"
    STABLE = "stable"


class ManifestVersion(IntEnum):
    """Enumeration of supported Visual Studio manifest versions."""

    VS2017 = 15
    VS2019 = 16
    VS2022 = 17
    VS2026 = 18

    @classmethod
    def channels_for(cls, version: Self) -> tuple[Channel, ...]:
        """Returns the valid channels for a given manifest version."""
        return (Channel.STABLE, Channel.INSIDERS) if version >= cls.VS2026 else (Channel.RELEASE, Channel.PREVIEW)


class VisualStudioInstallerOptions(BaseModel, validate_assignment=True):
    """Holds the runtime configuration that will be used to install packages from Visual Studio."""

    accept_license: bool
    cache_dir: Path
    channel_manifest_path: Path | None
    channel: Channel
    manifest_version: ManifestVersion
    workloads: list[str]

    @classmethod
    def get_default_manifest_options(cls) -> Self:
        """Returns the default manifest options for pyxwin.

        :returns: The default manifest options.

        """
        return cls(
            accept_license=False,
            cache_dir=user_cache_path("pyxwin", "pyxwin") / "msvcrt",
            channel_manifest_path=None,
            channel=Channel.STABLE,
            manifest_version=ManifestVersion.VS2026,
            workloads=["Microsoft.VisualStudio.Workload.VCTools"],
        )
