"""Service-level tests raising coverage on user/workspace administration."""

import pytest

from tests.conftest import create_user
from zen.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from zen.core.pagination import PageParams
from zen.db.base import get_session_factory
from zen.services.users import UserService
from zen.services.workspaces import WorkspaceService


async def test_user_service_listing_and_search(app):
    await create_user("user", "searchme")
    await create_user("user", "other")
    factory = get_session_factory()
    async with factory() as db:
        service = UserService(db)
        page = await service.list_users(PageParams(page=1, size=10))
        assert page.total == 2
        filtered = await service.list_users(PageParams(page=1, size=10), query="searchme")
        assert filtered.total == 1
        assert filtered.items[0].username == "searchme"


async def test_user_service_get_missing(app):
    factory = get_session_factory()
    async with factory() as db:
        with pytest.raises(NotFoundError):
            await UserService(db).get("nonexistent-id")


async def test_role_change_safeguards(app):
    admin = await create_user("admin", "boss")
    worker = await create_user("user", "worker")
    factory = get_session_factory()
    async with factory() as db:
        service = UserService(db)
        admin_db = await service.get(admin.id)
        # Last admin cannot demote themselves.
        with pytest.raises(ConflictError):
            await service.set_role(admin.id, "user", acting_admin=admin_db)
        # Invalid role rejected.
        with pytest.raises(ValidationFailed):
            await service.set_role(worker.id, "superuser", acting_admin=admin_db)
        # Promote then demote the other user.
        promoted = await service.set_role(worker.id, "admin", acting_admin=admin_db)
        assert promoted.role == "admin"
        # Now the original admin can step down (another admin exists).
        demoted = await service.set_role(admin.id, "user", acting_admin=admin_db)
        assert demoted.role == "user"


async def test_disable_and_delete_safeguards(app):
    admin = await create_user("admin", "chief")
    worker = await create_user("user", "minion")
    factory = get_session_factory()
    async with factory() as db:
        service = UserService(db)
        admin_db = await service.get(admin.id)
        with pytest.raises(ConflictError):
            await service.set_active(admin.id, False, acting_admin=admin_db)
        with pytest.raises(ConflictError):
            await service.delete(admin.id, acting_admin=admin_db)
        disabled = await service.set_active(worker.id, False, acting_admin=admin_db)
        assert disabled.is_active is False
        await service.delete(worker.id, acting_admin=admin_db)
        with pytest.raises(NotFoundError):
            await service.get(worker.id)


async def test_admin_password_reset_validation(app):
    user = await create_user("user", "pwuser")
    factory = get_session_factory()
    async with factory() as db:
        service = UserService(db)
        with pytest.raises(ValidationFailed):
            await service.admin_set_password(user.id, "short")
        updated = await service.admin_set_password(user.id, "a-totally-new-password")
        assert updated.password_hash


async def test_update_profile_validation(app):
    user = await create_user("user", "profiled")
    factory = get_session_factory()
    async with factory() as db:
        service = UserService(db)
        user_db = await service.get(user.id)
        updated = await service.update_profile(
            user_db, {"display_name": "  Display  ", "email": "x@example.com"}
        )
        assert updated.display_name == "Display"
        assert updated.email == "x@example.com"
        with pytest.raises(ValidationFailed):
            await service.update_profile(user_db, {"email": "not-an-email"})
        # Clearing email works.
        cleared = await service.update_profile(user_db, {"email": ""})
        assert cleared.email is None


async def test_preferences_validation(app):
    user = await create_user("user", "prefuser")
    factory = get_session_factory()
    async with factory() as db:
        service = UserService(db)
        user_db = await service.get(user.id)
        prefs = await service.update_preferences(
            user_db,
            {"theme": "dark", "default_mode": "focus", "keyboard_shortcuts": {"k": "cmd"}},
        )
        assert prefs.theme == "dark"
        with pytest.raises(ValidationFailed):
            await service.update_preferences(user_db, {"theme": "neon"})
        with pytest.raises(ValidationFailed):
            await service.update_preferences(user_db, {"default_mode": "turbo"})
        with pytest.raises(ValidationFailed):
            await service.update_preferences(user_db, {"keyboard_shortcuts": "oops"})


async def test_workspace_service_lifecycle(app):
    user = await create_user("user", "wsowner")
    factory = get_session_factory()
    async with factory() as db:
        service = WorkspaceService(db)
        from zen.services.users import UserService

        user_db = await UserService(db).get(user.id)
        with pytest.raises(ValidationFailed):
            await service.create(user_db, name="   ")
        workspace = await service.create(user_db, name="Lab", description="d")
        listed = await service.list_for_user(user_db)
        assert len(listed) == 1
        with pytest.raises(ValidationFailed):
            await service.update(workspace.id, user_db, {"name": "  "})
        with pytest.raises(ValidationFailed):
            await service.update(workspace.id, user_db, {"status": "bogus"})
        updated = await service.update(workspace.id, user_db, {"status": "archived"})
        assert updated.status == "archived"
        assert await service.list_for_user(user_db) == []
        assert len(await service.list_for_user(user_db, include_archived=True)) == 1
        overview = await service.overview(workspace.id, user_db)
        assert overview["bookmark_count"] == 0
        await service.delete(workspace.id, user_db)
        with pytest.raises(NotFoundError):
            await service.get_owned(workspace.id, user_db)


async def test_workspace_limit_enforced(app):
    user = await create_user("user", "limited")
    factory = get_session_factory()
    async with factory() as db:
        from zen.services.settings import SettingsService
        from zen.services.users import UserService

        await SettingsService(db).set("workspaces.max_per_user", 1)
        SettingsService.invalidate_local()
        user_db = await UserService(db).get(user.id)
        service = WorkspaceService(db)
        await service.create(user_db, name="First")
        with pytest.raises(ValidationFailed, match="limit"):
            await service.create(user_db, name="Second")


async def test_scheduled_tasks_run_against_real_db(app):
    """Exercise the worker task bodies (purge, retention, repo sync, metrics)."""
    from zen.workers.tasks import (
        enforce_history_retention,
        purge_expired_sessions,
        refresh_session_metrics,
        sync_plugin_repositories,
    )

    await purge_expired_sessions()
    await enforce_history_retention()
    await sync_plugin_repositories()
    await refresh_session_metrics()


async def test_provider_probe_task(app, db_session):
    """Probe task with all providers freshly healthy → no live probes attempted."""
    import respx

    from zen.search import health as provider_health
    from zen.search.providers import all_providers
    from zen.workers.tasks import probe_provider_health

    for slug in all_providers():
        await provider_health.record_success(slug, 100)

    with respx.mock:  # no routes mocked → any network attempt raises loudly
        await probe_provider_health()
