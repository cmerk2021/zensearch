"""API tests: workspaces, bookmarks, collections, tags, notes, history, exports."""


async def test_workspace_crud(user_client):
    created = await user_client.post(
        "/api/v1/workspaces",
        json={"name": "Kubernetes Lab", "description": "Cluster build research"},
    )
    assert created.status_code == 201
    workspace = created.json()

    listed = (await user_client.get("/api/v1/workspaces")).json()
    assert len(listed) == 1

    updated = await user_client.patch(
        f"/api/v1/workspaces/{workspace['id']}", json={"name": "K8s Lab", "color": "#7c9885"}
    )
    assert updated.json()["name"] == "K8s Lab"

    archived = await user_client.patch(
        f"/api/v1/workspaces/{workspace['id']}", json={"status": "archived"}
    )
    assert archived.json()["status"] == "archived"
    assert (await user_client.get("/api/v1/workspaces")).json() == []

    deleted = await user_client.delete(f"/api/v1/workspaces/{workspace['id']}")
    assert deleted.status_code == 200


async def test_workspace_isolation_between_users(app, user_client, admin_client):
    workspace = (
        await user_client.post("/api/v1/workspaces", json={"name": "Private"})
    ).json()
    # Another (admin) account can access for moderation; a normal second user cannot.
    from httpx import ASGITransport, AsyncClient

    from tests.conftest import create_user, login

    await create_user("user", "mallory")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://zen.test") as other:
        await login(other, "mallory")
        response = await other.get(f"/api/v1/workspaces/{workspace['id']}")
        assert response.status_code == 403


async def test_bookmark_crud_and_dedupe(user_client):
    payload = {
        "url": "https://docs.k3s.io/installation?utm_source=newsletter",
        "title": "K3s install docs",
        "source_provider": "google",
        "source_query": "k3s install",
    }
    created = await user_client.post("/api/v1/bookmarks", json=payload)
    assert created.status_code == 201
    bookmark = created.json()
    assert bookmark["url"] == "https://docs.k3s.io/installation"  # tracking stripped
    assert bookmark["domain"] == "docs.k3s.io"

    # Same canonical URL → idempotent, no duplicate.
    again = await user_client.post(
        "/api/v1/bookmarks", json={"url": "https://docs.k3s.io/installation"}
    )
    assert again.json()["id"] == bookmark["id"]
    page = (await user_client.get("/api/v1/bookmarks")).json()
    assert page["total"] == 1

    updated = await user_client.patch(
        f"/api/v1/bookmarks/{bookmark['id']}", json={"is_favorite": True}
    )
    assert updated.json()["is_favorite"] is True

    favorites = (await user_client.get("/api/v1/bookmarks?favorites=true")).json()
    assert favorites["total"] == 1

    search = (await user_client.get("/api/v1/bookmarks?q=k3s")).json()
    assert search["total"] == 1

    deleted = await user_client.delete(f"/api/v1/bookmarks/{bookmark['id']}")
    assert deleted.status_code == 200


async def test_bookmark_invalid_url_rejected(user_client):
    response = await user_client.post("/api/v1/bookmarks", json={"url": "javascript:alert(1)"})
    assert response.status_code == 422


async def test_tags_hierarchy_and_assignment(user_client):
    parent = (await user_client.post("/api/v1/tags", json={"name": "Tech"})).json()
    child = (
        await user_client.post("/api/v1/tags", json={"name": "Linux", "parent_id": parent["id"]})
    ).json()
    assert child["parent_id"] == parent["id"]

    # Cycle rejection.
    cycle = await user_client.patch(
        f"/api/v1/tags/{parent['id']}", json={"parent_id": child["id"]}
    )
    assert cycle.status_code == 422

    bookmark = (
        await user_client.post(
            "/api/v1/bookmarks",
            json={"url": "https://archlinux.org/", "tag_ids": [child["id"]]},
        )
    ).json()
    assert bookmark["tags"][0]["name"] == "Linux"

    tags = (await user_client.get("/api/v1/tags")).json()
    linux = next(t for t in tags if t["tag"]["name"] == "Linux")
    assert linux["bookmark_count"] == 1

    filtered = (await user_client.get(f"/api/v1/bookmarks?tag_id={child['id']}")).json()
    assert filtered["total"] == 1


async def test_collections_manual_and_smart(user_client):
    bookmark = (
        await user_client.post(
            "/api/v1/bookmarks", json={"url": "https://github.com/zensearch/zen"}
        )
    ).json()
    manual = (
        await user_client.post("/api/v1/collections", json={"name": "Read Later"})
    ).json()
    add = await user_client.put(
        f"/api/v1/collections/{manual['id']}/bookmarks/{bookmark['id']}"
    )
    assert add.status_code == 200
    contents = (
        await user_client.get(f"/api/v1/collections/{manual['id']}/bookmarks")
    ).json()
    assert len(contents) == 1

    smart = (
        await user_client.post(
            "/api/v1/collections",
            json={
                "name": "GitHub stuff",
                "is_smart": True,
                "rules": {
                    "match": "all",
                    "conditions": [
                        {"field": "domain", "operator": "equals", "value": "github.com"}
                    ],
                },
            },
        )
    ).json()
    smart_contents = (
        await user_client.get(f"/api/v1/collections/{smart['id']}/bookmarks")
    ).json()
    assert len(smart_contents) == 1
    assert smart_contents[0]["domain"] == "github.com"

    # Cannot manually add to smart collections.
    blocked = await user_client.put(
        f"/api/v1/collections/{smart['id']}/bookmarks/{bookmark['id']}"
    )
    assert blocked.status_code == 409

    # Invalid rules rejected.
    invalid = await user_client.post(
        "/api/v1/collections",
        json={
            "name": "Bad",
            "is_smart": True,
            "rules": {"match": "all", "conditions": [{"field": "nope", "operator": "equals", "value": "x"}]},
        },
    )
    assert invalid.status_code == 422


async def test_notes_with_revisions_and_links(user_client):
    note = (
        await user_client.post(
            "/api/v1/notes", json={"title": "Cluster plan", "content": "# Plan\n\nUse k3s."}
        )
    ).json()

    updated = await user_client.patch(
        f"/api/v1/notes/{note['id']}",
        json={"content": "# Plan v2\n\nUse k3s with etcd."},
    )
    assert "v2" in updated.json()["content"]

    revisions = (await user_client.get(f"/api/v1/notes/{note['id']}/revisions")).json()
    assert len(revisions) == 1

    restored = await user_client.post(
        f"/api/v1/notes/{note['id']}/revisions/{revisions[0]['id']}/restore"
    )
    assert "Use k3s." in restored.json()["content"]

    # Search by content.
    found = (await user_client.get("/api/v1/notes?q=k3s")).json()
    assert found["total"] == 1

    # Link note → bookmark.
    bookmark = (
        await user_client.post("/api/v1/bookmarks", json={"url": "https://k3s.io/"})
    ).json()
    link = await user_client.post(
        f"/api/v1/notes/{note['id']}/links",
        json={"target_type": "bookmark", "target_id": bookmark["id"]},
    )
    assert link.status_code == 201
    detail = (await user_client.get(f"/api/v1/notes/{note['id']}")).json()
    assert len(detail["links"]) == 1

    # Self-link rejected.
    self_link = await user_client.post(
        f"/api/v1/notes/{note['id']}/links",
        json={"target_type": "note", "target_id": note["id"]},
    )
    assert self_link.status_code == 422


async def test_workspace_export(user_client):
    workspace = (
        await user_client.post("/api/v1/workspaces", json={"name": "Export me"})
    ).json()
    await user_client.post(
        "/api/v1/bookmarks",
        json={"url": "https://example.com/a", "workspace_id": workspace["id"]},
    )
    await user_client.post(
        "/api/v1/notes",
        json={"title": "N", "content": "Body", "workspace_id": workspace["id"]},
    )
    data = (await user_client.get(f"/api/v1/workspaces/{workspace['id']}/export.json")).json()
    assert data["format"] == "zen.workspace.v1"
    assert len(data["bookmarks"]) == 1
    assert len(data["notes"]) == 1

    zip_response = await user_client.get(f"/api/v1/workspaces/{workspace['id']}/export.zip")
    assert zip_response.status_code == 200
    assert zip_response.headers["content-type"] == "application/zip"

    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
        names = zf.namelist()
        assert "README.md" in names
        assert "bookmarks.md" in names
        assert any(n.startswith("notes/") for n in names)


async def test_bookmarks_html_export(user_client):
    await user_client.post("/api/v1/bookmarks", json={"url": "https://example.com/x"})
    response = await user_client.get("/api/v1/bookmarks/export.html")
    assert response.status_code == 200
    assert "NETSCAPE-Bookmark-file-1" in response.text


async def test_takeout_export(user_client):
    await user_client.post("/api/v1/bookmarks", json={"url": "https://example.com/y"})
    data = (await user_client.get("/api/v1/me/export.json")).json()
    assert data["format"] == "zen.takeout.v1"
    assert data["unfiled"]["bookmarks"]


async def test_preferences_roundtrip(user_client):
    prefs = (await user_client.get("/api/v1/me/preferences")).json()
    assert prefs["theme"] == "system"
    updated = await user_client.patch(
        "/api/v1/me/preferences",
        json={"theme": "amoled", "default_mode": "focus", "keyboard_shortcuts": {"search": "/"}},
    )
    assert updated.json()["theme"] == "amoled"
    invalid = await user_client.patch("/api/v1/me/preferences", json={"theme": "neon"})
    assert invalid.status_code == 422
