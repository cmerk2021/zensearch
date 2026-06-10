"""Knowledge routes: workspaces, bookmarks, collections, tags, notes, history."""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from zen.api.deps import DB, CurrentUser, Writer
from zen.core.pagination import Page, PageParams
from zen.schemas.api import (
    BookmarkCreate,
    BookmarkOut,
    BookmarkUpdate,
    CollectionCreate,
    CollectionOut,
    CollectionUpdate,
    HistoryEntryOut,
    NoteCreate,
    NoteLinkCreate,
    NoteLinkOut,
    NoteListItem,
    NoteOut,
    NoteRevisionOut,
    NoteUpdate,
    TagCreate,
    TagOut,
    TagUpdate,
    TagWithCounts,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from zen.schemas.common import Message
from zen.services.bookmarks import BookmarkService
from zen.services.collections import CollectionService
from zen.services.export import ExportService
from zen.services.history import HistoryService
from zen.services.notes import NoteService
from zen.services.tags import TagService
from zen.services.workspaces import WorkspaceService

router = APIRouter(tags=["knowledge"])


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(
    user: CurrentUser, db: DB, include_archived: bool = False
) -> list[WorkspaceOut]:
    workspaces = await WorkspaceService(db).list_for_user(
        user, include_archived=include_archived
    )
    return [WorkspaceOut.model_validate(w) for w in workspaces]


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(payload: WorkspaceCreate, user: Writer, db: DB) -> WorkspaceOut:
    workspace = await WorkspaceService(db).create(
        user,
        name=payload.name,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
    )
    return WorkspaceOut.model_validate(workspace)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(workspace_id: str, user: CurrentUser, db: DB) -> WorkspaceOut:
    workspace = await WorkspaceService(db).get_owned(workspace_id, user)
    return WorkspaceOut.model_validate(workspace)


@router.get("/workspaces/{workspace_id}/overview")
async def workspace_overview(workspace_id: str, user: CurrentUser, db: DB) -> dict:
    data = await WorkspaceService(db).overview(workspace_id, user)
    return {
        "workspace": WorkspaceOut.model_validate(data["workspace"]).model_dump(),
        "bookmark_count": data["bookmark_count"],
        "note_count": data["note_count"],
        "search_count": data["search_count"],
        "recent_searches": [
            HistoryEntryOut.model_validate(s).model_dump() for s in data["recent_searches"]
        ],
    }


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: str, payload: WorkspaceUpdate, user: Writer, db: DB
) -> WorkspaceOut:
    workspace = await WorkspaceService(db).update(
        workspace_id, user, payload.model_dump(exclude_unset=True)
    )
    return WorkspaceOut.model_validate(workspace)


@router.delete("/workspaces/{workspace_id}", response_model=Message)
async def delete_workspace(workspace_id: str, user: Writer, db: DB) -> Message:
    await WorkspaceService(db).delete(workspace_id, user)
    return Message(message="Workspace deleted.")


@router.get("/workspaces/{workspace_id}/export.json")
async def export_workspace_json(workspace_id: str, user: CurrentUser, db: DB) -> dict:
    return await ExportService(db).export_workspace_json(workspace_id, user)


@router.get("/workspaces/{workspace_id}/export.zip")
async def export_workspace_zip(workspace_id: str, user: CurrentUser, db: DB) -> Response:
    blob = await ExportService(db).export_workspace_markdown_zip(workspace_id, user)
    return Response(
        content=blob,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="workspace-export.zip"'},
    )


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------


@router.get("/bookmarks", response_model=Page[BookmarkOut])
async def list_bookmarks(
    user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    q: str | None = None,
    workspace_id: str | None = None,
    tag_id: str | None = None,
    domain: str | None = None,
    favorites: bool = False,
    include_archived: bool = False,
) -> Page[BookmarkOut]:
    result = await BookmarkService(db).list_for_user(
        user,
        PageParams(page=page, size=size),
        query=q,
        workspace_id=workspace_id,
        tag_id=tag_id,
        domain=domain,
        favorites_only=favorites,
        include_archived=include_archived,
    )
    return Page(
        items=[BookmarkOut.model_validate(b) for b in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
    )


@router.post("/bookmarks", response_model=BookmarkOut, status_code=201)
async def create_bookmark(payload: BookmarkCreate, user: Writer, db: DB) -> BookmarkOut:
    bookmark = await BookmarkService(db).create(
        user,
        url=payload.url,
        title=payload.title,
        description=payload.description,
        snippet=payload.snippet,
        workspace_id=payload.workspace_id,
        source_provider=payload.source_provider,
        source_query=payload.source_query,
        tag_ids=payload.tag_ids,
    )
    return BookmarkOut.model_validate(bookmark)


@router.get("/bookmarks/export.html")
async def export_bookmarks(user: CurrentUser, db: DB) -> Response:
    html = await ExportService(db).export_bookmarks_html(user)
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="zen-bookmarks.html"'},
    )


@router.get("/bookmarks/{bookmark_id}", response_model=BookmarkOut)
async def get_bookmark(bookmark_id: str, user: CurrentUser, db: DB) -> BookmarkOut:
    bookmark = await BookmarkService(db).get_owned(bookmark_id, user)
    return BookmarkOut.model_validate(bookmark)


@router.patch("/bookmarks/{bookmark_id}", response_model=BookmarkOut)
async def update_bookmark(
    bookmark_id: str, payload: BookmarkUpdate, user: Writer, db: DB
) -> BookmarkOut:
    bookmark = await BookmarkService(db).update(
        bookmark_id, user, payload.model_dump(exclude_unset=True)
    )
    return BookmarkOut.model_validate(bookmark)


@router.delete("/bookmarks/{bookmark_id}", response_model=Message)
async def delete_bookmark(bookmark_id: str, user: Writer, db: DB) -> Message:
    await BookmarkService(db).delete(bookmark_id, user)
    return Message(message="Bookmark deleted.")


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(user: CurrentUser, db: DB) -> list[CollectionOut]:
    collections = await CollectionService(db).list_for_user(user)
    return [CollectionOut.model_validate(c) for c in collections]


@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(payload: CollectionCreate, user: Writer, db: DB) -> CollectionOut:
    collection = await CollectionService(db).create(
        user,
        name=payload.name,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        is_smart=payload.is_smart,
        rules=payload.rules,
    )
    return CollectionOut.model_validate(collection)


@router.get("/collections/{collection_id}", response_model=CollectionOut)
async def get_collection(collection_id: str, user: CurrentUser, db: DB) -> CollectionOut:
    collection = await CollectionService(db).get_owned(collection_id, user)
    return CollectionOut.model_validate(collection)


@router.get("/collections/{collection_id}/bookmarks", response_model=list[BookmarkOut])
async def collection_bookmarks(
    collection_id: str, user: CurrentUser, db: DB
) -> list[BookmarkOut]:
    bookmarks = await CollectionService(db).bookmarks_in(collection_id, user)
    return [BookmarkOut.model_validate(b) for b in bookmarks]


@router.patch("/collections/{collection_id}", response_model=CollectionOut)
async def update_collection(
    collection_id: str, payload: CollectionUpdate, user: Writer, db: DB
) -> CollectionOut:
    collection = await CollectionService(db).update(
        collection_id, user, payload.model_dump(exclude_unset=True)
    )
    return CollectionOut.model_validate(collection)


@router.delete("/collections/{collection_id}", response_model=Message)
async def delete_collection(collection_id: str, user: Writer, db: DB) -> Message:
    await CollectionService(db).delete(collection_id, user)
    return Message(message="Collection deleted.")


@router.put("/collections/{collection_id}/bookmarks/{bookmark_id}", response_model=Message)
async def add_to_collection(
    collection_id: str, bookmark_id: str, user: Writer, db: DB
) -> Message:
    await CollectionService(db).add_bookmark(collection_id, bookmark_id, user)
    return Message(message="Added to collection.")


@router.delete("/collections/{collection_id}/bookmarks/{bookmark_id}", response_model=Message)
async def remove_from_collection(
    collection_id: str, bookmark_id: str, user: Writer, db: DB
) -> Message:
    await CollectionService(db).remove_bookmark(collection_id, bookmark_id, user)
    return Message(message="Removed from collection.")


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@router.get("/tags", response_model=list[TagWithCounts])
async def list_tags(user: CurrentUser, db: DB) -> list[TagWithCounts]:
    rows = await TagService(db).list_for_user(user)
    return [
        TagWithCounts(
            tag=TagOut.model_validate(row["tag"]),
            bookmark_count=row["bookmark_count"],
            note_count=row["note_count"],
        )
        for row in rows
    ]


@router.post("/tags", response_model=TagOut, status_code=201)
async def create_tag(payload: TagCreate, user: Writer, db: DB) -> TagOut:
    tag = await TagService(db).create(
        user, name=payload.name, parent_id=payload.parent_id, color=payload.color
    )
    return TagOut.model_validate(tag)


@router.patch("/tags/{tag_id}", response_model=TagOut)
async def update_tag(tag_id: str, payload: TagUpdate, user: Writer, db: DB) -> TagOut:
    tag = await TagService(db).update(tag_id, user, payload.model_dump(exclude_unset=True))
    return TagOut.model_validate(tag)


@router.delete("/tags/{tag_id}", response_model=Message)
async def delete_tag(tag_id: str, user: Writer, db: DB) -> Message:
    await TagService(db).delete(tag_id, user)
    return Message(message="Tag deleted.")


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


@router.get("/notes", response_model=Page[NoteListItem])
async def list_notes(
    user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    q: str | None = None,
    workspace_id: str | None = None,
    tag_id: str | None = None,
) -> Page[NoteListItem]:
    result = await NoteService(db).list_for_user(
        user, PageParams(page=page, size=size), query=q, workspace_id=workspace_id, tag_id=tag_id
    )
    return Page(
        items=[NoteListItem.model_validate(n) for n in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
    )


@router.post("/notes", response_model=NoteOut, status_code=201)
async def create_note(payload: NoteCreate, user: Writer, db: DB) -> NoteOut:
    note = await NoteService(db).create(
        user,
        title=payload.title,
        content=payload.content,
        workspace_id=payload.workspace_id,
        tag_ids=payload.tag_ids,
    )
    return NoteOut.model_validate(note)


@router.get("/notes/{note_id}", response_model=NoteOut)
async def get_note(note_id: str, user: CurrentUser, db: DB) -> NoteOut:
    note = await NoteService(db).get_owned(note_id, user)
    return NoteOut.model_validate(note)


@router.patch("/notes/{note_id}", response_model=NoteOut)
async def update_note(note_id: str, payload: NoteUpdate, user: Writer, db: DB) -> NoteOut:
    note = await NoteService(db).update(note_id, user, payload.model_dump(exclude_unset=True))
    return NoteOut.model_validate(note)


@router.delete("/notes/{note_id}", response_model=Message)
async def delete_note(note_id: str, user: Writer, db: DB) -> Message:
    await NoteService(db).delete(note_id, user)
    return Message(message="Note deleted.")


@router.get("/notes/{note_id}/revisions", response_model=list[NoteRevisionOut])
async def note_revisions(note_id: str, user: CurrentUser, db: DB) -> list[NoteRevisionOut]:
    revisions = await NoteService(db).revisions(note_id, user)
    return [NoteRevisionOut.model_validate(r) for r in revisions]


@router.post("/notes/{note_id}/revisions/{revision_id}/restore", response_model=NoteOut)
async def restore_note_revision(
    note_id: str, revision_id: str, user: Writer, db: DB
) -> NoteOut:
    note = await NoteService(db).restore_revision(note_id, revision_id, user)
    return NoteOut.model_validate(note)


@router.post("/notes/{note_id}/links", response_model=NoteLinkOut, status_code=201)
async def add_note_link(
    note_id: str, payload: NoteLinkCreate, user: Writer, db: DB
) -> NoteLinkOut:
    link = await NoteService(db).add_link(
        note_id, user, target_type=payload.target_type, target_id=payload.target_id
    )
    return NoteLinkOut.model_validate(link)


@router.delete("/notes/{note_id}/links/{link_id}", response_model=Message)
async def remove_note_link(note_id: str, link_id: str, user: Writer, db: DB) -> Message:
    await NoteService(db).remove_link(note_id, link_id, user)
    return Message(message="Link removed.")


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@router.get("/history", response_model=Page[HistoryEntryOut])
async def list_history(
    user: CurrentUser,
    db: DB,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    q: str | None = None,
    workspace_id: str | None = None,
) -> Page[HistoryEntryOut]:
    result = await HistoryService(db).list_for_user(
        user, PageParams(page=page, size=size), query=q, workspace_id=workspace_id
    )
    return Page(
        items=[HistoryEntryOut.model_validate(h) for h in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
    )


@router.delete("/history", response_model=Message)
async def clear_history(user: CurrentUser, db: DB) -> Message:
    count = await HistoryService(db).clear_for_user(user)
    return Message(message=f"Cleared {count} entries.")


@router.delete("/history/{entry_id}", response_model=Message)
async def delete_history_entry(entry_id: str, user: CurrentUser, db: DB) -> Message:
    await HistoryService(db).delete_entry(entry_id, user)
    return Message(message="Entry deleted.")
