"""Audit logging for security-relevant actions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen.core.pagination import Page, PageParams
from zen.db.models import AuditLogEntry


async def record(
    db: AsyncSession,
    *,
    action: str,
    actor_id: str | None = None,
    target_type: str = "",
    target_id: str = "",
    data: dict[str, Any] | None = None,
    ip_address: str = "",
    commit: bool = True,
) -> None:
    """Append an audit entry. Never raises — auditing must not break requests."""
    try:
        from zen.services.settings import SettingsService

        enabled = await SettingsService(db).get("security.audit_enabled", True)
        if not enabled:
            return
        db.add(
            AuditLogEntry(
                action=action,
                actor_id=actor_id,
                target_type=target_type,
                target_id=str(target_id) if target_id else "",
                data=data or {},
                ip_address=ip_address,
            )
        )
        if commit:
            await db.commit()
    except Exception:
        import structlog

        structlog.get_logger(__name__).exception("audit.record_failed", action=action)


async def list_entries(
    db: AsyncSession,
    page_params: PageParams,
    *,
    action: str | None = None,
    actor_id: str | None = None,
) -> Page[AuditLogEntry]:
    from sqlalchemy import func

    query = select(AuditLogEntry)
    if action:
        query = query.where(AuditLogEntry.action == action)
    if actor_id:
        query = query.where(AuditLogEntry.actor_id == actor_id)
    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()
    rows = (
        (
            await db.execute(
                query.order_by(AuditLogEntry.created_at.desc())
                .offset(page_params.offset)
                .limit(page_params.size)
            )
        )
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page_params.page, size=page_params.size)
