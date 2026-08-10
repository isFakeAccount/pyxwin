"""Modules for resolving all the packages necessary for installing Visual Studio Workload."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from pyxwin.core.pyxwin_exceptions import PyxwinError
from pyxwin.wincrt_sdk.manifest_datatypes import ItemType

if TYPE_CHECKING:
    from pyxwin.wincrt_sdk.manifest_datatypes import Architecture, ManifestPayload, PyxwinPackages, VisualStudioInstallerOptions


def get_workload_names(pyxwin_packages: PyxwinPackages) -> list[str]:
    """Gets the list of workload names from the manifest packages.

    :param pyxwin_packages: The manifest containing all available packages.

    :returns: A list of workload names.

    """
    workload_names: list[str] = []
    for workload_name, workload_per_arch in pyxwin_packages.items():
        for package in workload_per_arch.values():
            if package.type == ItemType.WORKLOAD:
                workload_names.append(workload_name)
                break  # No need to check other architectures for the same workload

    return sorted(workload_names)


def resolve_workload_payloads(pyxwin_packages: PyxwinPackages, installer_options: VisualStudioInstallerOptions) -> dict[str, dict[str, list[ManifestPayload]]]:
    """Resolves the payloads required for the specified workloads in the manifest options.

    :param pyxwin_packages: The manifest containing all available packages.
    :param installer_options: The options for the Visual Studio installer.

    :returns: A dictionary mapping workloads to architectures and their required ManifestPayloads.

    """
    workload_payloads: dict[str, dict[str, list[ManifestPayload]]] = defaultdict(dict)
    for workload in installer_options.workloads:
        if workload not in pyxwin_packages:
            raise PyxwinError(f"Workload '{workload}' not found in the manifest.")

        workload_packages = pyxwin_packages[workload]
        for arch, package in workload_packages.items():
            if package.dependencies is None:
                continue
            workload_payloads[workload][arch] = list(resolve_dependency_payloads(pyxwin_packages, arch, package.dependencies))

    return workload_payloads


def resolve_dependency_payloads(pyxwin_packages: PyxwinPackages, arch: Architecture, dependencies: dict[str, Any]) -> set[ManifestPayload]:
    """Recursively resolves the payloads for a given set of dependencies.

    :param pyxwin_packages: The manifest containing all available packages.
    :param arch: The architecture for which to resolve the payloads.
    :param dependencies: A dictionary of dependencies to resolve.

    :returns: A set of ManifestPayloads required for the given dependencies and architecture.

    """
    fl_payloads: set[ManifestPayload] = set()
    for dependency, dep_metadata in dependencies.items():
        if isinstance(dep_metadata, dict):
            dep_type: str = dep_metadata.get("type", "required").lower()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
            if dep_type not in ["recommended", "required"]:
                continue

        dependency_pkg = pyxwin_packages.get(dependency, {}).get(arch)
        if dependency_pkg is None:
            continue

        if dependency_pkg.payloads is not None:
            fl_payloads.update(dependency_pkg.payloads)

        if dependency_pkg.dependencies is None:
            continue

        nested_payloads = resolve_dependency_payloads(pyxwin_packages, arch, dependency_pkg.dependencies)
        fl_payloads.update(nested_payloads)
    return fl_payloads
