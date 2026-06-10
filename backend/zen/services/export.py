"""Export service: workspaces, bookmarks, and notes in portable formats."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zen.db.models import Bookmark, Note, SearchHistory, User, Workspace
from zen.services.workspaces import WorkspaceService


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class ExportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def export_workspace_json(self, workspace_id: str, user: User) -> dict:
        workspace = await WorkspaceService(self.db).get_owned(workspace_id, user)
        bookmarks = (
            await self.db.execute(
                select(Bookmark)
                .options(selectinload(Bookmark.tags))
                .where(Bookmark.workspace_id == workspace.id)
                .order_by(Bookmark.created_at)
            )
        ).scalars().all()
        notes = (
            await self.db.execute(
                select(Note)
                .options(selectinload(Note.tags))
                .where(Note.workspace_id == workspace.id)
                .order_by(Note.created_at)
            )
        ).scalars().all()
        searches = (
            await self.db.execute(
                select(SearchHistory)
                .where(SearchHistory.workspace_id == workspace.id)
                .order_by(SearchHistory.created_at)
            )
        ).scalars().all()
        return {
            "format": "zen.workspace.v1",
            "exported_at": datetime.now().astimezone().isoformat(),
            "workspace": {
                "name": workspace.name,
                "description": workspace.description,
                "icon": workspace.icon,
                "color": workspace.color,
                "created_at": _iso(workspace.created_at),
            },
            "bookmarks": [
                {
                    "url": b.url,
                    "title": b.title,
                    "description": b.description,
                    "snippet": b.snippet,
                    "domain": b.domain,
                    "source_provider": b.source_provider,
                    "source_query": b.source_query,
                    "is_favorite": b.is_favorite,
                    "tags": [t.name for t in b.tags],
                    "created_at": _iso(b.created_at),
                }
                for b in bookmarks
            ],
            "notes": [
                {
                    "title": n.title,
                    "content": n.content,
                    "tags": [t.name for t in n.tags],
                    "created_at": _iso(n.created_at),
                    "updated_at": _iso(n.updated_at),
                }
                for n in notes
            ],
            "searches": [
                {
                    "query": s.query,
                    "mode": s.mode,
                    "result_count": s.result_count,
                    "created_at": _iso(s.created_at),
                }
                for s in searches
            ],
        }

    async def export_workspace_markdown_zip(self, workspace_id: str, user: User) -> bytes:
        """Markdown bundle: README + notes as .md files + bookmarks list."""
        data = await self.export_workspace_json(workspace_id, user)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            ws = data["workspace"]
            readme = [f"# {ws['name']}", ""]
            if ws["description"]:
                readme += [ws["description"], ""]
            readme += [
                f"Exported from Zen on {data['exported_at']}",
                "",
                f"- Bookmarks: {len(data['bookmarks'])}",
                f"- Notes: {len(data['notes'])}",
                f"- Searches: {len(data['searches'])}",
            ]
            zf.writestr("README.md", "\n".join(readme))

            bookmark_lines = ["# Bookmarks", ""]
            for b in data["bookmarks"]:
                bookmark_lines.append(f"- [{b['title'] or b['url']}]({b['url']})")
                if b["snippet"]:
                    bookmark_lines.append(f"  - {b['snippet']}")
                if b["tags"]:
                    bookmark_lines.append(f"  - Tags: {', '.join(b['tags'])}")
            zf.writestr("bookmarks.md", "\n".join(bookmark_lines))

            used_names: set[str] = set()
            for note in data["notes"]:
                base = "".join(
                    c for c in (note["title"] or "untitled") if c.isalnum() or c in " -_"
                ).strip()[:60] or "untitled"
                name = base
                counter = 1
                while name in used_names:
                    counter += 1
                    name = f"{base}-{counter}"
                used_names.add(name)
                front = f"# {note['title']}\n\n"
                zf.writestr(f"notes/{name}.md", front + note["content"])

            searches_lines = ["# Search history", ""]
            for s in data["searches"]:
                searches_lines.append(f"- `{s['query']}` ({s['mode']}, {s['created_at']})")
            zf.writestr("searches.md", "\n".join(searches_lines))

            zf.writestr("workspace.json", json.dumps(data, indent=2, ensure_ascii=False))
        return buffer.getvalue()

    async def export_bookmarks_html(self, user: User) -> str:
        """Netscape bookmark file (importable by every browser)."""
        bookmarks = (
            await self.db.execute(
                select(Bookmark)
                .where(Bookmark.owner_id == user.id, Bookmark.is_archived.is_(False))
                .order_by(Bookmark.created_at)
            )
        ).scalars().all()
        lines = [
            "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            "<TITLE>Bookmarks</TITLE>",
            "<H1>Zen bookmarks</H1>",
            "<DL><p>",
        ]
        for b in bookmarks:
            ts = int(b.created_at.timestamp()) if b.created_at else 0
            title = (b.title or b.url).replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f'    <DT><A HREF="{b.url}" ADD_DATE="{ts}">{title}</A>')
        lines.append("</DL><p>")
        return "\n".join(lines)

    async def export_all_json(self, user: User) -> dict:
        """Full personal data export (GDPR-style takeout)."""
        workspaces = (
            await self.db.execute(select(Workspace).where(Workspace.owner_id == user.id))
        ).scalars().all()
        result = {
            "format": "zen.takeout.v1",
            "exported_at": datetime.now().astimezone().isoformat(),
            "user": {"username": user.username, "display_name": user.display_name},
            "workspaces": [],
            "unfiled": None,
        }
        for ws in workspaces:
            result["workspaces"].append(await self.export_workspace_json(ws.id, user))
        # Items without workspace
        bookmarks = (
            await self.db.execute(
                select(Bookmark)
                .options(selectinload(Bookmark.tags))
                .where(Bookmark.owner_id == user.id, Bookmark.workspace_id.is_(None))
            )
        ).scalars().all()
        notes = (
            await self.db.execute(
                select(Note)
                .options(selectinload(Note.tags))
                .where(Note.owner_id == user.id, Note.workspace_id.is_(None))
            )
        ).scalars().all()
        result["unfiled"] = {
            "bookmarks": [
                {"url": b.url, "title": b.title, "tags": [t.name for t in b.tags]}
                for b in bookmarks
            ],
            "notes": [
                {"title": n.title, "content": n.content, "tags": [t.name for t in n.tags]}
                for n in notes
            ],
        }
        return result
