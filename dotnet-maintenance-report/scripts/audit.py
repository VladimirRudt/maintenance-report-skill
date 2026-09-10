#!/usr/bin/env python3
"""Python equivalent of audit.ps1: dependency audit report generator.

Usage:
    python audit.py --mode core --solution <path>.sln
    python audit.py --mode framework --config-paths a/packages.config b/packages.config
"""
import argparse
import json
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PackageEntry:
    package: str
    current_version: str
    latest_version: str | None  # None means the lookup failed
    is_vulnerable: bool | None  # None means the vulnerability check failed
    projects: list[str] = field(default_factory=list)

    @property
    def is_up_to_date(self) -> bool:
        return self.latest_version is not None and self.current_version == self.latest_version


@dataclass
class PackageGroup:
    current_versions: list[str]
    latest_version: str | None
    is_vulnerable: bool | None
    projects: list[str]
    packages: list[str]

    @property
    def package(self) -> str | None:
        return self.packages[0] if len(self.packages) == 1 else None

    @property
    def prefix(self) -> str:
        return self.packages[0].split(".")[0]

    @property
    def display_name(self) -> str:
        if self.package:
            return self.package
        return f"<details><summary>{self.prefix}.* </summary>{''.join(map(lambda x: f'<li>{x}</li>', self.packages))}</details>"

    @property
    def display_current_version(self) -> str:
        return ", ".join(self.current_versions) if len(self.current_versions) > 1 else self.current_versions[0]

    @property
    def display_latest_version(self) -> str:
        return self.latest_version if self.latest_version is not None else "Unknown (lookup failed)"

    @property
    def display_vulnerable(self) -> str:
        if self.is_vulnerable is None:
            return "Unknown (check failed)"
        return "Yes" if self.is_vulnerable else "No"

    @property
    def display_packages(self) -> str:
        return f"<ul>{''.join(map(lambda x: f'<li>{x}</li>', self.projects))}</ul>"

    @property
    def sort_key(self) -> str:
        return self.package or f"{self.prefix}.*"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def run_dotnet_list(path: str, flag: str) -> dict:
    result = subprocess.run(
        ["dotnet", "list", path, "package", flag, "--format", "json"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        fail(f"'dotnet list package {flag}' failed:\n{result.stderr}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        fail(f"Failed to parse 'dotnet list package {flag}' output: {e}")


def get_latest_nuget_version(package_id: str) -> str | None:
    try:
        uri = f"https://api.nuget.org/v3-flatcontainer/{package_id.lower()}/index.json"
        with urllib.request.urlopen(uri, timeout=10) as resp:
            data = json.loads(resp.read())
        versions = data.get("versions", [])
        stable = [v for v in versions if "-" not in v]
        return (stable or versions or [None])[-1]
    except Exception:
        return None


def get_latest_nuget_versions(package_ids: list[str]) -> dict[str, str | None]:
    # NuGet has no bulk lookup endpoint, so requests are parallelized instead of batched.
    with ThreadPoolExecutor(max_workers=8) as executor:
        return dict(zip(package_ids, executor.map(get_latest_nuget_version, package_ids)))


def is_nuget_vulnerable(package_id: str, version: str) -> bool | None:
    try:
        body = json.dumps({
            "package": {"name": package_id, "ecosystem": "NuGet"},
            "version": version,
        }).encode()
        req = urllib.request.Request(
            "https://api.osv.dev/v1/query", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            response = json.loads(resp.read())
        return bool(response.get("vulns"))
    except Exception:
        return None


def check_vulnerabilities(packages_map: dict[str, PackageEntry]) -> None:
    # OSV.dev has no bulk lookup endpoint, so requests are parallelized instead of batched.
    entries = list(packages_map.values())
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(lambda e: is_nuget_vulnerable(e.package, e.current_version), entries)
    for entry, vulnerable in zip(entries, results):
        entry.is_vulnerable = vulnerable


def parse_legacy_packages(config_path: Path) -> list[tuple[str, str]]:
    try:
        tree = ET.parse(config_path)
    except Exception as e:
        fail(f"Failed to read '{config_path}': {e}")
    return [(pkg.get("id"), pkg.get("version")) for pkg in tree.getroot().findall("package")]


def merge_legacy_package_data(config_paths: list[str], packages_map: dict[str, PackageEntry]) -> None:
    configs = []
    for config_path in config_paths:
        path = Path(config_path)
        if not path.is_file():
            fail(f"packages.config path not found: '{config_path}'")
        configs.append((path, parse_legacy_packages(path)))

    all_package_ids = [pkg_id for _, packages in configs for pkg_id, _ in packages]
    latest_versions = get_latest_nuget_versions(sorted(set(all_package_ids)))

    for path, packages in configs:
        project_name = path.parent.name
        for pkg_id, pkg_version in packages:
            entry = packages_map.setdefault(
                pkg_id, PackageEntry(pkg_id, pkg_version, latest_versions.get(pkg_id), False))
            entry.latest_version = latest_versions.get(pkg_id) or entry.latest_version
            if project_name not in entry.projects:
                entry.projects.append(project_name)


def merge_package_data(data: dict, packages_map: dict[str, PackageEntry]) -> None:
    for project in data.get("projects") or []:
        project_name = Path(project["path"]).name

        for fw in project.get("frameworks", []):
            for pkg in [*fw.get("topLevelPackages", []), *fw.get("transitivePackages", [])]:
                entry = packages_map.setdefault(pkg["id"], PackageEntry(
                    pkg["id"], pkg.get("resolvedVersion"), pkg.get("latestVersion"), False,
                ))

                entry.latest_version = pkg.get("latestVersion") or entry.latest_version

                if project_name not in entry.projects:
                    entry.projects.append(project_name)


def group_packages(packages_map: dict[str, PackageEntry]) -> list[PackageGroup]:
    groups: dict[str, PackageGroup] = {}
    for entry in packages_map.values():
        if entry.is_up_to_date:
            continue
        namespace = entry.package.split(".")[0]
        group_key = f"{entry.latest_version}|{namespace}"
        group = groups.setdefault(group_key, PackageGroup([], entry.latest_version, False, [], []))
        if entry.current_version not in group.current_versions:
            group.current_versions.append(entry.current_version)
        if group.is_vulnerable is not True:
            group.is_vulnerable = True if entry.is_vulnerable else (None if entry.is_vulnerable is None else group.is_vulnerable)
        group.packages.append(entry.package)
        group.projects.extend(p for p in entry.projects if p not in group.projects)
    return sorted(groups.values(), key=lambda g: (g.is_vulnerable is not True, g.sort_key))


def build_table(groups: list[PackageGroup]) -> str:
    header = [
        "| Package | Current Version | Latest Version | Vulnerable | Projects |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    rows = [
        f"| {g.display_name} | {g.display_current_version} | {g.display_latest_version} | "
        f"{g.display_vulnerable} | {g.display_packages} |"
        for g in groups
    ]
    return "\n".join(header + rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a dependency audit report.")
    parser.add_argument("--mode", choices=["core", "framework"], default="core",
                         help="'core' uses 'dotnet list package' (SDK-style projects); "
                              "'framework' audits explicit packages.config files (classic .NET Framework).")
    parser.add_argument("--solution", help="Target solution/project path (required for --mode core).")
    parser.add_argument("--config-paths", nargs="+",
                         help="Explicit packages.config file paths (required for --mode framework).")
    args = parser.parse_args()

    if args.mode == "core" and not args.solution:
        fail("--mode core requires --solution.")
    if args.mode == "framework" and not args.config_paths:
        fail("--mode framework requires --config-paths pointing to packages.config file(s).")
    return args


def main() -> None:
    args = parse_args()
    packages_map: dict[str, PackageEntry] = {}

    if args.mode == "core":
        merge_package_data(run_dotnet_list(args.solution, "--outdated"), packages_map)
    else:
        merge_legacy_package_data(args.config_paths, packages_map)

    check_vulnerabilities(packages_map)

    groups = group_packages(packages_map)
    full_table = build_table(groups) if groups else "All packages are up to date and no vulnerabilities were found."

    print(full_table)


if __name__ == "__main__":
    main()
