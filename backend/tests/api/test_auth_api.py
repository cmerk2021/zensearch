"""API tests: authentication, sessions, CSRF, roles."""


from tests.conftest import create_user, login


async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readiness(client):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["database"] is True
    assert body["checks"]["cache"] is True


async def test_login_logout_flow(client):
    await create_user("user", "bob")
    body = await login(client, "bob")
    assert body["username"] == "bob"
    assert "zen_session" in dict(client.cookies)

    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["username"] == "bob"

    out = await client.post("/api/v1/auth/logout")
    assert out.status_code == 200


async def test_invalid_credentials(client):
    await create_user("user", "carol")
    response = await client.post(
        "/api/v1/auth/login", json={"username": "carol", "password": "wrong-password-99"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_unknown_user_same_error(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "ghost", "password": "whatever-pw-123"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_anonymous_me_unauthorized(client):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


async def test_csrf_required_on_unsafe_methods(client):
    await create_user("user", "dave")
    await login(client, "dave")
    # Remove CSRF header → mutation must fail.
    client.headers.pop("X-CSRF-Token", None)
    response = await client.post("/api/v1/workspaces", json={"name": "X"})
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failure"


async def test_csrf_wrong_token_rejected(client):
    await create_user("user", "erin")
    await login(client, "erin")
    client.headers["X-CSRF-Token"] = "forged-token"
    response = await client.post("/api/v1/workspaces", json={"name": "X"})
    assert response.status_code == 403


async def test_registration_closed_by_default(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "newbie", "password": "a-long-enough-pw-1"},
    )
    assert response.status_code == 403


async def test_registration_when_open(admin_client, client):
    response = await admin_client.put(
        "/api/v1/admin/settings", json={"values": {"auth.registration": "open"}}
    )
    assert response.status_code == 200
    from zen.services.settings import SettingsService

    SettingsService.invalidate_local()
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "newbie", "password": "a-long-enough-pw-1"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "user"


async def test_weak_password_rejected_on_admin_create(admin_client):
    response = await admin_client.post(
        "/api/v1/admin/users",
        json={"username": "weak", "password": "password123", "role": "user"},
    )
    assert response.status_code == 422


async def test_readonly_cannot_write(readonly_client):
    response = await readonly_client.post("/api/v1/workspaces", json={"name": "Nope"})
    assert response.status_code == 403


async def test_user_cannot_access_admin(user_client):
    response = await user_client.get("/api/v1/admin/settings")
    assert response.status_code == 403


async def test_session_listing_and_revocation(client):
    await create_user("user", "frank")
    await login(client, "frank")
    sessions = (await client.get("/api/v1/auth/sessions")).json()
    assert len(sessions) == 1
    response = await client.post("/api/v1/auth/sessions/revoke-all")
    assert response.status_code == 200


async def test_change_password(client):
    await create_user("user", "grace")
    await login(client, "grace")
    response = await client.post(
        "/api/v1/auth/password",
        json={
            "current_password": "sufficiently-long-pw-1",
            "new_password": "a-brand-new-passphrase-2",
        },
    )
    assert response.status_code == 200
    # Old password no longer works.
    fail = await client.post(
        "/api/v1/auth/login",
        json={"username": "grace", "password": "sufficiently-long-pw-1"},
    )
    assert fail.status_code == 401
    ok = await client.post(
        "/api/v1/auth/login",
        json={"username": "grace", "password": "a-brand-new-passphrase-2"},
    )
    assert ok.status_code == 200


async def test_auth_rate_limiting(client):
    for _attempt in range(10):
        await client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "wrong-pw-123456"}
        )
    response = await client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "wrong-pw-123456"}
    )
    assert response.status_code == 429
    assert "Retry-After" in response.headers


async def test_first_run_setup_flow(client):
    info = (await client.get("/api/v1/meta/instance")).json()
    assert info["bootstrap_required"] is True
    response = await client.post(
        "/api/v1/meta/setup",
        json={"username": "firstadmin", "password": "first-admin-pass-1"},
    )
    assert response.status_code == 200
    info = (await client.get("/api/v1/meta/instance")).json()
    assert info["bootstrap_required"] is False
    # Second attempt is rejected.
    again = await client.post(
        "/api/v1/meta/setup", json={"username": "x", "password": "another-pass-12345"}
    )
    assert again.status_code == 403
