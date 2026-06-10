"""Unit tests for the plugin platform (manifest, SDK permissions, lifecycle)."""

import json
import zipfile
from io import BytesIO

import pytest

from zen.core.exceptions import PluginError, PluginPermissionError
from zen.plugins.manifest import parse_manifest
from zen.plugins.sdk import PluginContext, plugin_bangs, unload_context

VALID_MANIFEST = {
    "id": "test-plugin",
    "name": "Test Plugin",
    "version": "1.0.0",
    "entry": "test_plugin",
    "permissions": ["bangs"],
}


def test_parse_valid_manifest():
    manifest = parse_manifest(VALID_MANIFEST)
    assert manifest.id == "test-plugin"
    assert manifest.permissions == ["bangs"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"id": ""},
        {"id": "Has Spaces"},
        {"id": "UPPER"},
        {"version": "not-a-version"},
        {"entry": "1bad.module"},
        {"permissions": ["unknown_capability"]},
        {"permissions": "bangs"},
        {"sdk_version": "99.0"},
    ],
)
def test_parse_invalid_manifests(mutation):
    data = {**VALID_MANIFEST, **mutation}
    with pytest.raises(PluginError):
        parse_manifest(data)


def test_min_zen_version_enforced():
    data = {**VALID_MANIFEST, "min_zen_version": "999.0.0"}
    with pytest.raises(PluginError, match="requires Zen"):
        parse_manifest(data)


def test_context_permission_gating():
    ctx = PluginContext(slug="p", permissions=frozenset({"bangs"}))
    ctx.register_bang("test", "https://example.com/?q={q}")
    assert plugin_bangs().get("test") == "https://example.com/?q={q}"

    with pytest.raises(PluginPermissionError):
        ctx.register_theme("t", {"name": "T", "colors": {}})

    unload_context(ctx)
    assert "test" not in plugin_bangs()


def test_context_rejects_bad_bang():
    ctx = PluginContext(slug="p", permissions=frozenset({"bangs"}))
    with pytest.raises(ValueError):
        ctx.register_bang("bad", "https://example.com/no-placeholder")


def test_register_provider_through_context():
    from zen.search.providers import all_providers
    from zen.search.providers.base import SearchProvider

    class MyProvider(SearchProvider):
        slug = "test-custom-provider"
        name = "Test Custom"

        async def search(self, query, client):
            return []

    ctx = PluginContext(slug="p", permissions=frozenset({"search_providers"}))
    ctx.register_search_provider(MyProvider)
    assert "test-custom-provider" in all_providers()
    unload_context(ctx)
    assert "test-custom-provider" not in all_providers()


def test_provider_slug_conflict_rejected():
    from zen.search.providers.base import SearchProvider

    class Impostor(SearchProvider):
        slug = "google"  # conflicts with builtin
        name = "Impostor"

        async def search(self, query, client):
            return []

    ctx = PluginContext(slug="p", permissions=frozenset({"search_providers"}))
    with pytest.raises(ValueError, match="conflicts"):
        ctx.register_search_provider(Impostor)


def make_plugin_zip(manifest: dict, code: str = "def setup(ctx):\n    pass\n") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("zen-plugin.json", json.dumps(manifest))
        zf.writestr(f"{manifest['entry']}.py", code)
    return buffer.getvalue()


async def test_install_from_bytes_and_lifecycle(app, db_session, tmp_path):
    from zen.plugins.manager import PluginManager

    manifest = {
        "id": "lifecycle-plugin",
        "name": "Lifecycle",
        "version": "1.0.0",
        "entry": "lifecycle_plugin",
        "permissions": ["bangs"],
    }
    code = (
        "def setup(ctx):\n"
        "    ctx.register_bang('lifecycle', 'https://example.com/?q={q}')\n"
    )
    blob = make_plugin_zip(manifest, code)
    manager = PluginManager(db_session)
    plugin = await manager.install_from_bytes(blob)
    assert plugin.status == "enabled"
    assert plugin_bangs().get("lifecycle")

    # Duplicate same-version install is rejected.
    from zen.core.exceptions import ConflictError

    with pytest.raises(ConflictError):
        await manager.install_from_bytes(blob)

    # Upgrade.
    manifest_v2 = {**manifest, "version": "2.0.0"}
    plugin = await manager.install_from_bytes(make_plugin_zip(manifest_v2, code))
    assert plugin.version == "2.0.0"
    assert plugin.previous_version == "1.0.0"

    # Rollback.
    plugin = await manager.rollback("lifecycle-plugin")
    assert plugin.version == "1.0.0"

    # Disable removes registrations.
    await manager.set_enabled("lifecycle-plugin", False)
    assert "lifecycle" not in plugin_bangs()

    # Remove.
    await manager.remove("lifecycle-plugin")
    from zen.core.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await manager.get("lifecycle-plugin")


async def test_zip_slip_rejected(app, db_session):
    from zen.plugins.manager import PluginManager

    buffer = BytesIO()
    manifest = {
        "id": "evil-plugin",
        "name": "Evil",
        "version": "1.0.0",
        "entry": "evil",
        "permissions": [],
    }
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("zen-plugin.json", json.dumps(manifest))
        zf.writestr("../../outside.py", "print('escaped')")
    with pytest.raises(PluginError, match="unsafe path"):
        await PluginManager(db_session).install_from_bytes(buffer.getvalue())


async def test_broken_setup_reports_error(app, db_session):
    from zen.plugins.manager import PluginManager

    manifest = {
        "id": "broken-plugin",
        "name": "Broken",
        "version": "1.0.0",
        "entry": "broken_plugin",
        "permissions": [],
    }
    blob = make_plugin_zip(manifest, "def setup(ctx):\n    raise RuntimeError('boom')\n")
    plugin = await PluginManager(db_session).install_from_bytes(blob)
    assert plugin.status == "error"
    assert "boom" in plugin.error
