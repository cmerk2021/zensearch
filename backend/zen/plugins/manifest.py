"""Plugin manifest schema and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from packaging.version import InvalidVersion, Version

from zen.core.exceptions import PluginError
from zen.plugins.sdk import CAPABILITIES
from zen.version import SDK_VERSION, __version__

MANIFEST_FILENAME = "zen-plugin.json"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
_MODULE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")


@dataclass(slots=True)
class PluginManifest:
    id: str
    name: str
    version: str
    entry: str
    description: str = ""
    author: str = ""
    license: str = ""
    homepage: str = ""
    permissions: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    min_zen_version: str = ""
    sdk_version: str = "1.0"
    types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "entry": self.entry,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "permissions": self.permissions,
            "requires": self.requires,
            "min_zen_version": self.min_zen_version,
            "sdk_version": self.sdk_version,
            "types": self.types,
        }


def parse_manifest(data: dict) -> PluginManifest:
    if not isinstance(data, dict):
        raise PluginError("Manifest must be a JSON object.")

    def _req_str(key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PluginError(f"Manifest field '{key}' is required and must be a string.")
        return value.strip()

    plugin_id = _req_str("id")
    if not _SLUG_RE.match(plugin_id):
        raise PluginError(
            "Manifest 'id' must be 3-64 chars of lowercase letters, digits and hyphens."
        )
    name = _req_str("name")
    version = _req_str("version")
    try:
        Version(version)
    except InvalidVersion as exc:
        raise PluginError(f"Manifest 'version' is not a valid version: {version}") from exc
    entry = _req_str("entry")
    if not _MODULE_RE.match(entry):
        raise PluginError(f"Manifest 'entry' is not a valid Python module path: {entry}")

    permissions = data.get("permissions", [])
    if not isinstance(permissions, list) or not all(isinstance(p, str) for p in permissions):
        raise PluginError("Manifest 'permissions' must be a list of strings.")
    unknown = sorted(set(permissions) - CAPABILITIES)
    if unknown:
        raise PluginError(f"Manifest declares unknown permissions: {', '.join(unknown)}")

    requires = data.get("requires", [])
    if not isinstance(requires, list) or not all(isinstance(r, str) for r in requires):
        raise PluginError("Manifest 'requires' must be a list of plugin ids.")

    sdk_version = str(data.get("sdk_version", "1.0"))
    if sdk_version.split(".")[0] != SDK_VERSION.split(".")[0]:
        raise PluginError(
            f"Plugin targets SDK {sdk_version}; this Zen provides SDK {SDK_VERSION}."
        )

    min_zen = str(data.get("min_zen_version", "") or "")
    if min_zen:
        try:
            if Version(__version__) < Version(min_zen):
                raise PluginError(
                    f"Plugin requires Zen >= {min_zen}; this instance is {__version__}."
                )
        except InvalidVersion as exc:
            raise PluginError(f"Invalid 'min_zen_version': {min_zen}") from exc

    types = data.get("types", [])
    if not isinstance(types, list):
        raise PluginError("Manifest 'types' must be a list.")

    return PluginManifest(
        id=plugin_id,
        name=name,
        version=version,
        entry=entry,
        description=str(data.get("description", "")),
        author=str(data.get("author", "")),
        license=str(data.get("license", "")),
        homepage=str(data.get("homepage", "")),
        permissions=list(permissions),
        requires=list(requires),
        min_zen_version=min_zen,
        sdk_version=sdk_version,
        types=[str(t) for t in types] or list(permissions),
    )
