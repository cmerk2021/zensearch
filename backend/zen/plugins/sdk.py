"""Plugin SDK — the stable surface plugins build against.

Versioning contract: ``SDK_VERSION`` (major.minor) only changes minor for
additive changes; breaking changes bump major and Zen refuses to load plugins
built for a different major (see ``zen.plugins.manifest``).

A plugin ships a ``zen-plugin.json`` manifest and an entry module exposing::

    def setup(ctx: zen.plugins.sdk.PluginContext) -> None: ...

The context only exposes capabilities the manifest declares under
``permissions`` — undeclared access raises :class:`PluginPermissionError`
(ADR-0007: review boundary, not a security sandbox).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from zen.core.exceptions import PluginPermissionError
from zen.version import SDK_VERSION  # noqa: F401  (re-exported for plugins)

log = structlog.get_logger(__name__)

#: Capabilities a plugin may request via manifest ``permissions``.
CAPABILITIES = frozenset(
    {
        "search_providers",
        "rankers",
        "bangs",
        "themes",
        "exporters",
        "ai_backends",
        "widgets",
    }
)

#: Registries populated by plugins, consumed by the application.
_plugin_bangs: dict[str, str] = {}
_plugin_themes: dict[str, dict] = {}
_plugin_exporters: dict[str, Callable] = {}
_plugin_widgets: dict[str, dict] = {}


def plugin_bangs() -> dict[str, str]:
    return dict(_plugin_bangs)


def plugin_themes() -> dict[str, dict]:
    return dict(_plugin_themes)


def plugin_exporters() -> dict[str, Callable]:
    return dict(_plugin_exporters)


def plugin_widgets() -> dict[str, dict]:
    return dict(_plugin_widgets)


@dataclass
class PluginContext:
    """Capability gateway handed to a plugin's ``setup`` function."""

    slug: str
    permissions: frozenset[str]
    config: dict[str, Any] = field(default_factory=dict)
    #: Registration bookkeeping so a plugin can be cleanly unloaded.
    _registered: dict[str, list[str]] = field(default_factory=dict)

    def _require(self, capability: str) -> None:
        if capability not in CAPABILITIES:
            raise PluginPermissionError(f"Unknown capability: {capability}")
        if capability not in self.permissions:
            raise PluginPermissionError(
                f"Plugin '{self.slug}' did not declare the '{capability}' permission."
            )

    def _track(self, capability: str, key: str) -> None:
        self._registered.setdefault(capability, []).append(key)

    # -- capabilities ---------------------------------------------------

    def register_search_provider(self, provider_class: type) -> None:
        self._require("search_providers")
        from zen.search.providers import register_provider

        register_provider(provider_class, source=f"plugin:{self.slug}")
        self._track("search_providers", provider_class.slug)

    def register_ranker(self, ranker: Any) -> None:
        self._require("rankers")
        from zen.search.ranking import register_ranker

        register_ranker(ranker)
        self._track("rankers", ranker.name)

    def register_bang(self, bang: str, url_template: str) -> None:
        self._require("bangs")
        bang = bang.lstrip("!").lower()
        if not bang or "{q}" not in url_template:
            raise ValueError("A bang needs a name and a '{q}' placeholder in its template.")
        _plugin_bangs[bang] = url_template
        self._track("bangs", bang)

    def register_theme(self, theme_id: str, definition: dict) -> None:
        self._require("themes")
        required = {"name", "colors"}
        if not required.issubset(definition):
            raise ValueError(f"Theme definition requires keys: {sorted(required)}")
        _plugin_themes[theme_id] = {**definition, "plugin": self.slug}
        self._track("themes", theme_id)

    def register_exporter(self, format_id: str, exporter: Callable) -> None:
        self._require("exporters")
        _plugin_exporters[format_id] = exporter
        self._track("exporters", format_id)

    def register_ai_backend(self, name: str, factory: type) -> None:
        self._require("ai_backends")
        from zen.ai.base import register_backend

        register_backend(name, factory)
        self._track("ai_backends", name)

    def register_widget(self, widget_id: str, definition: dict) -> None:
        self._require("widgets")
        if "name" not in definition:
            raise ValueError("Widget definition requires a 'name'.")
        _plugin_widgets[widget_id] = {**definition, "plugin": self.slug}
        self._track("widgets", widget_id)


def unload_context(ctx: PluginContext) -> None:
    """Remove everything a plugin registered (reload/uninstall path)."""
    from zen.search.providers import unregister_provider
    from zen.search.ranking import unregister_ranker

    for slug in ctx._registered.get("search_providers", []):
        unregister_provider(slug)
    for name in ctx._registered.get("rankers", []):
        try:
            unregister_ranker(name)
        except ValueError:
            log.warning("plugin.unload_ranker_failed", plugin=ctx.slug, ranker=name)
    for bang in ctx._registered.get("bangs", []):
        _plugin_bangs.pop(bang, None)
    for theme in ctx._registered.get("themes", []):
        _plugin_themes.pop(theme, None)
    for fmt in ctx._registered.get("exporters", []):
        _plugin_exporters.pop(fmt, None)
    for widget in ctx._registered.get("widgets", []):
        _plugin_widgets.pop(widget, None)
    ctx._registered.clear()
