"""API tests: search execution with mocked providers, modes, profiles, admin."""

import httpx
import respx

GOOGLE_HTML = """
<html><body><div id="search">
  <div class="g"><a href="https://fastapi.tiangolo.com/"><h3>FastAPI</h3></a>
  <div class="VwiC3b">FastAPI is a modern, fast web framework for building APIs with Python that everyone seems to love.</div></div>
  <div class="g"><a href="https://flask.palletsprojects.com/"><h3>Flask</h3></a>
  <div class="VwiC3b">Flask is a lightweight WSGI web application framework designed for quick starts and scaling.</div></div>
</div></body></html>
"""

BING_HTML = """
<html><body><ol id="b_results">
  <li class="b_algo"><h2><a href="https://fastapi.tiangolo.com/">FastAPI framework</a></h2>
  <div class="b_caption"><p>High performance, easy to learn web framework.</p></div></li>
  <li class="b_algo"><h2><a href="https://www.djangoproject.com/">Django</a></h2>
  <div class="b_caption"><p>The web framework for perfectionists with deadlines.</p></div></li>
</ol></body></html>
"""


def mock_upstreams(google_status=200, bing_status=200):
    respx.get(url__regex=r"https://www\.google\.com/search.*").mock(
        return_value=httpx.Response(google_status, text=GOOGLE_HTML)
    )
    respx.get(url__regex=r"https://www\.bing\.com/search.*").mock(
        return_value=httpx.Response(bing_status, text=BING_HTML)
    )
    # All other providers fail fast (connection error) — tests degradation.
    respx.route().mock(side_effect=httpx.ConnectError("offline"))


@respx.mock
async def test_search_merges_and_ranks(user_client):
    mock_upstreams()
    response = await user_client.get(
        "/api/v1/search", params={"q": "python web framework", "providers": "google,bing"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "python web framework"
    urls = [r["url"] for r in body["results"]]
    assert "https://fastapi.tiangolo.com/" in urls
    fastapi_result = next(r for r in body["results"] if "fastapi" in r["url"])
    assert set(fastapi_result["providers"]) == {"google", "bing"}
    # Consensus result ranks first.
    assert body["results"][0]["url"] == "https://fastapi.tiangolo.com/"
    statuses = {p["slug"]: p for p in body["providers"]}
    assert statuses["google"]["ok"] is True
    assert statuses["bing"]["ok"] is True


@respx.mock
async def test_search_graceful_degradation(user_client):
    mock_upstreams(google_status=500)  # google now fails
    response = await user_client.get(
        "/api/v1/search", params={"q": "test", "providers": "google,bing"}
    )
    assert response.status_code == 200
    body = response.json()
    statuses = {p["slug"]: p for p in body["providers"]}
    assert statuses["google"]["ok"] is False
    assert statuses["bing"]["ok"] is True
    assert len(body["results"]) == 2  # bing-only results still served


@respx.mock
async def test_search_caching(user_client):
    mock_upstreams()
    first = (
        await user_client.get("/api/v1/search", params={"q": "cached", "providers": "google"})
    ).json()
    assert first["cached"] is False
    second = (
        await user_client.get("/api/v1/search", params={"q": "cached", "providers": "google"})
    ).json()
    assert second["cached"] is True
    assert [r["url"] for r in second["results"]] == [r["url"] for r in first["results"]]


@respx.mock
async def test_privacy_mode_no_history_no_cache(user_client):
    mock_upstreams()
    await user_client.get(
        "/api/v1/search", params={"q": "secret topic", "mode": "privacy", "providers": "google"}
    )
    history = (await user_client.get("/api/v1/history")).json()
    assert history["total"] == 0
    # Not served from cache on repeat.
    second = (
        await user_client.get(
            "/api/v1/search",
            params={"q": "secret topic", "mode": "privacy", "providers": "google"},
        )
    ).json()
    assert second["cached"] is False


@respx.mock
async def test_normal_mode_records_history(user_client):
    mock_upstreams()
    await user_client.get(
        "/api/v1/search", params={"q": "public topic", "providers": "google"}
    )
    history = (await user_client.get("/api/v1/history")).json()
    assert history["total"] == 1
    assert history["items"][0]["query"] == "public topic"


async def test_bang_redirect(user_client):
    response = await user_client.get("/api/v1/search", params={"q": "!gh zen search"})
    body = response.json()
    assert body["redirect"] == "https://github.com/search?q=zen+search"
    assert body["results"] == []


async def test_bangs_listing(user_client):
    bangs = (await user_client.get("/api/v1/search/bangs")).json()
    assert "gh" in bangs and "wiki" in bangs


@respx.mock
async def test_research_mode_associates_workspace(user_client):
    mock_upstreams()
    workspace = (
        await user_client.post("/api/v1/workspaces", json={"name": "Research"})
    ).json()
    response = (
        await user_client.get(
            "/api/v1/search",
            params={
                "q": "topic",
                "mode": "research",
                "workspace_id": workspace["id"],
                "providers": "google",
            },
        )
    ).json()
    assert response["workspace_id"] == workspace["id"]
    history = (
        await user_client.get("/api/v1/history", params={"workspace_id": workspace["id"]})
    ).json()
    assert history["total"] == 1


async def test_click_recording(user_client):
    response = await user_client.post(
        "/api/v1/search/click",
        json={"url": "https://example.com/page", "query": "test", "provider": "google"},
    )
    assert response.status_code == 200


async def test_suggestions_from_history(user_client):
    with respx.mock:
        mock_upstreams()
        await user_client.get(
            "/api/v1/search", params={"q": "kubernetes networking", "providers": "google"}
        )
    suggestions = (
        await user_client.get("/api/v1/search/suggest", params={"q": "kuber"})
    ).json()
    assert "kubernetes networking" in suggestions


async def test_profiles_listing(user_client):
    profiles = (await user_client.get("/api/v1/profiles")).json()
    slugs = {p["slug"] for p in profiles}
    assert {"balanced", "engineering", "privacy"} <= slugs
    default = next(p for p in profiles if p["is_default"])
    assert default["slug"] == "balanced"


@respx.mock
async def test_search_with_profile_provider_subset(user_client):
    mock_upstreams()
    body = (
        await user_client.get(
            "/api/v1/search", params={"q": "x", "profile": "privacy"}
        )
    ).json()
    attempted = {p["slug"] for p in body["providers"]}
    # The privacy profile excludes google/bing entirely.
    assert "google" not in attempted
    assert "bing" not in attempted
    assert body["profile_slug"] == "privacy"


# ---------------------------------------------------------------------------
# Admin surface
# ---------------------------------------------------------------------------


async def test_admin_provider_management(admin_client):
    providers = (await admin_client.get("/api/v1/admin/providers")).json()
    assert any(p["slug"] == "google" for p in providers)

    response = await admin_client.patch(
        "/api/v1/admin/providers/google", json={"enabled": False, "weight": 0.5}
    )
    assert response.status_code == 200
    providers = (await admin_client.get("/api/v1/admin/providers")).json()
    google = next(p for p in providers if p["slug"] == "google")
    assert google["enabled"] is False
    assert google["weight"] == 0.5


async def test_admin_provider_api_key_stored_encrypted(admin_client, db_session):
    response = await admin_client.patch(
        "/api/v1/admin/providers/brave", json={"api_key": "BSAxxxx-secret"}
    )
    assert response.status_code == 200
    from sqlalchemy import select

    from zen.db.models import ProviderConfig

    row = (
        await db_session.execute(select(ProviderConfig).where(ProviderConfig.slug == "brave"))
    ).scalar_one()
    assert row.api_key_encrypted.startswith("enc:v1:")
    assert "BSAxxxx-secret" not in row.api_key_encrypted


async def test_admin_settings_roundtrip_and_validation(admin_client):
    settings = (await admin_client.get("/api/v1/admin/settings")).json()
    assert settings["instance.name"] == "Zen"

    ok = await admin_client.put(
        "/api/v1/admin/settings",
        json={"values": {"instance.name": "My Zen", "search.safe_search": False}},
    )
    assert ok.status_code == 200

    bad_key = await admin_client.put(
        "/api/v1/admin/settings", json={"values": {"not.a.real.key": 1}}
    )
    assert bad_key.status_code == 422

    bad_type = await admin_client.put(
        "/api/v1/admin/settings", json={"values": {"search.safe_search": "yes"}}
    )
    assert bad_type.status_code == 422


async def test_admin_secret_settings_redacted(admin_client):
    await admin_client.put(
        "/api/v1/admin/settings", json={"values": {"ai.api_key": "sk-super-secret-key"}}
    )
    from zen.services.settings import SettingsService

    SettingsService.invalidate_local()
    settings = (await admin_client.get("/api/v1/admin/settings")).json()
    assert "sk-super-secret-key" not in str(settings)
    assert settings["ai.api_key"].startswith("••••")


async def test_admin_profile_crud(admin_client):
    created = await admin_client.post(
        "/api/v1/admin/profiles",
        json={"name": "Custom", "providers": ["duckduckgo"], "is_default": False},
    )
    assert created.status_code == 201
    profile = created.json()

    invalid = await admin_client.post(
        "/api/v1/admin/profiles", json={"name": "Bad", "providers": ["nonexistent"]}
    )
    assert invalid.status_code == 422

    updated = await admin_client.patch(
        f"/api/v1/admin/profiles/{profile['id']}", json={"description": "Edited"}
    )
    assert updated.json()["description"] == "Edited"

    deleted = await admin_client.delete(f"/api/v1/admin/profiles/{profile['id']}")
    assert deleted.status_code == 200


async def test_admin_cannot_delete_default_profile(admin_client):
    profiles = (await admin_client.get("/api/v1/admin/profiles")).json()
    default = next(p for p in profiles if p["is_default"])
    response = await admin_client.delete(f"/api/v1/admin/profiles/{default['id']}")
    assert response.status_code == 409


async def test_admin_domain_rules(admin_client):
    created = await admin_client.post(
        "/api/v1/admin/domain-rules",
        json={"domain": "www.SPAM.example", "action": "block"},
    )
    assert created.status_code == 201
    assert created.json()["domain"] == "spam.example"

    rules = (await admin_client.get("/api/v1/admin/domain-rules")).json()
    assert len(rules) == 1

    deleted = await admin_client.delete(f"/api/v1/admin/domain-rules/{rules[0]['id']}")
    assert deleted.status_code == 200


async def test_admin_user_management_safeguards(admin_client):
    created = (
        await admin_client.post(
            "/api/v1/admin/users",
            json={"username": "worker", "password": "a-long-password-12", "role": "user"},
        )
    ).json()

    promoted = await admin_client.patch(
        f"/api/v1/admin/users/{created['id']}", json={"role": "admin"}
    )
    assert promoted.json()["role"] == "admin"

    # The acting admin cannot delete itself.
    me = (await admin_client.get("/api/v1/me")).json()
    response = await admin_client.delete(f"/api/v1/admin/users/{me['id']}")
    assert response.status_code == 409

    # Demote the other admin back; works because one admin remains.
    demoted = await admin_client.patch(
        f"/api/v1/admin/users/{created['id']}", json={"role": "user"}
    )
    assert demoted.json()["role"] == "user"


async def test_per_user_ai_access(app, user_client, admin_client, db_session):
    from zen.services.settings import SettingsService

    # Enable AI on the instance and configure a model.
    settings = SettingsService(db_session)
    await settings.set_many({"ai.enabled": True, "ai.model": "llama3.2"})
    SettingsService.invalidate_local()

    # New users have AI disabled by default.
    me = (await user_client.get("/api/v1/me")).json()
    assert me["ai_enabled"] is False

    status = (await user_client.get("/api/v1/ai/status")).json()
    assert status["enabled"] is False

    # AI capabilities are rejected while access is not granted.
    denied = await user_client.post(
        "/api/v1/ai/summarize", json={"q": "python", "results": []}
    )
    assert denied.status_code == 403

    # Admin grants AI access to the user.
    granted = await admin_client.patch(
        f"/api/v1/admin/users/{me['id']}", json={"ai_enabled": True}
    )
    assert granted.status_code == 200
    assert granted.json()["ai_enabled"] is True

    # The user now sees AI as available.
    status2 = (await user_client.get("/api/v1/ai/status")).json()
    assert status2["enabled"] is True


async def test_admin_created_user_defaults_ai_disabled(admin_client):
    created = (
        await admin_client.post(
            "/api/v1/admin/users",
            json={"username": "granted", "password": "a-long-password-12", "ai_enabled": True},
        )
    ).json()
    assert created["ai_enabled"] is True

    default_off = (
        await admin_client.post(
            "/api/v1/admin/users",
            json={"username": "plain", "password": "a-long-password-12"},
        )
    ).json()
    assert default_off["ai_enabled"] is False


async def test_admin_audit_log_populated(admin_client):
    await admin_client.put(
        "/api/v1/admin/settings", json={"values": {"instance.tagline": "x"}}
    )
    audit = (await admin_client.get("/api/v1/admin/audit")).json()
    actions = [e["action"] for e in audit["items"]]
    assert "settings.updated" in actions


async def test_admin_diagnostics(admin_client):
    response = await admin_client.get("/api/v1/admin/diagnostics")
    assert response.status_code == 200
    body = response.json()
    assert body["database"]["ok"] is True
    assert body["cache"]["ok"] is True


async def test_provider_health_endpoint(admin_client):
    response = await admin_client.get("/api/v1/admin/providers/health")
    assert response.status_code == 200
    body = response.json()
    assert "google" in body
    assert body["google"]["state"] == "closed"


async def test_metrics_admin_gated(admin_client, client):
    anonymous = await client.get("/metrics")
    assert anonymous.status_code == 403
    authorized = await admin_client.get("/metrics")
    assert authorized.status_code == 200
    assert b"zen_build_info" in authorized.content
