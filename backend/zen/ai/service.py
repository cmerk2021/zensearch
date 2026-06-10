"""AI capabilities: query expansion, summaries, digests, reports, knowledge maps.

Every capability is grounded in explicit context passed to the model — never
in retained conversation state — and degrades gracefully when AI is disabled
or unreachable (the product is fully functional without AI).
"""

from __future__ import annotations

import json
import re
import time

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from zen.ai.base import ChatMessage, ChatOptions, build_backend
from zen.core.exceptions import AIUnavailableError
from zen.db.models import Bookmark, Note, SearchHistory, User
from zen.observability import metrics
from zen.search.models import SearchResult
from zen.services.settings import SettingsService
from zen.services.workspaces import WorkspaceService

log = structlog.get_logger(__name__)

MAX_CONTEXT_RESULTS = 12
MAX_CONTEXT_BOOKMARKS = 40
MAX_CONTEXT_NOTES = 15
MAX_NOTE_CHARS = 1500


class AIService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = SettingsService(db)

    async def _get_backend_and_options(self) -> tuple:
        if not await self.settings.get("ai.enabled", False):
            raise AIUnavailableError("AI features are disabled on this instance.")
        backend_name = await self.settings.get("ai.backend", "ollama")
        base_url = await self.settings.get("ai.base_url", "")
        api_key = await self.settings.get("ai.api_key", "")
        model = await self.settings.get("ai.model", "")
        if not model:
            raise AIUnavailableError("No AI model is configured.")
        backend = build_backend(backend_name, base_url=base_url, api_key=api_key)
        options = ChatOptions(
            model=model,
            temperature=float(await self.settings.get("ai.temperature", 0.3)),
            max_tokens=int(await self.settings.get("ai.max_tokens", 1024)),
            timeout_seconds=float(await self.settings.get("ai.timeout_seconds", 120)),
        )
        return backend, options

    async def _chat(self, capability: str, messages: list[ChatMessage]) -> str:
        backend, options = await self._get_backend_and_options()
        started = time.perf_counter()
        try:
            result = await backend.chat(messages, options)
            metrics.AI_REQUESTS.labels(capability=capability, outcome="ok").inc()
            return result
        except AIUnavailableError:
            metrics.AI_REQUESTS.labels(capability=capability, outcome="error").inc()
            raise
        finally:
            metrics.AI_LATENCY.labels(capability=capability).observe(
                time.perf_counter() - started
            )

    async def status(self) -> dict:
        enabled = await self.settings.get("ai.enabled", False)
        info = {
            "enabled": bool(enabled),
            "backend": await self.settings.get("ai.backend", "ollama"),
            "model": await self.settings.get("ai.model", ""),
            "reachable": False,
            "models": [],
        }
        if not enabled:
            return info
        try:
            backend, _ = await self._get_backend_and_options()
            info["reachable"] = await backend.ping()
            if info["reachable"]:
                info["models"] = (await backend.list_models())[:50]
        except AIUnavailableError as exc:
            info["error"] = str(exc)
        return info

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    async def expand_query(self, query: str) -> list[str]:
        """Generate up to five improved/alternative search queries."""
        prompt = (
            "You are a search query refinement assistant. Given the user's query, "
            "produce 3-5 alternative search queries that would surface better or "
            "complementary results: more specific phrasings, synonyms, expert "
            "terminology, or decompositions.\n\n"
            "Respond with ONLY a JSON array of strings, no commentary.\n\n"
            f"Query: {query!r}"
        )
        raw = await self._chat("expand_query", [ChatMessage(role="user", content=prompt)])
        suggestions = _parse_string_array(raw)
        cleaned = [s.strip() for s in suggestions if s.strip() and s.strip().lower() != query.lower()]
        return cleaned[:5]

    async def summarize_results(self, query: str, results: list[SearchResult]) -> str:
        """Summarize a result set with numbered source citations."""
        subset = results[:MAX_CONTEXT_RESULTS]
        if not subset:
            raise AIUnavailableError("Nothing to summarize: the result set is empty.")
        sources = "\n".join(
            f"[{i + 1}] {r.title}\n    URL: {r.url}\n    {r.snippet or '(no snippet)'}"
            for i, r in enumerate(subset)
        )
        prompt = (
            "Summarize what these search results collectively say about the query. "
            "Be factual and concise (under 250 words). Cite sources inline using "
            "bracketed numbers like [1], [3] that refer to the numbered list. Do not "
            "invent information that is not present in the snippets.\n\n"
            f"Query: {query}\n\nResults:\n{sources}"
        )
        return await self._chat(
            "summarize_results", [ChatMessage(role="user", content=prompt)]
        )

    async def research_digest(self, workspace_id: str, user: User) -> str:
        """Narrative overview of everything captured in a workspace."""
        context = await self._workspace_context(workspace_id, user)
        prompt = (
            "You are a research assistant. Produce a digest of this research "
            "workspace in Markdown: a 2-3 sentence overview, key themes as "
            "bullet points, notable sources worth revisiting, and open questions "
            "implied by the recent searches. Ground every statement in the "
            "provided material; do not invent sources.\n\n" + context
        )
        return await self._chat("research_digest", [ChatMessage(role="user", content=prompt)])

    async def workspace_report(self, workspace_id: str, user: User) -> str:
        """Long-form structured report assembled from workspace materials."""
        context = await self._workspace_context(workspace_id, user)
        prompt = (
            "Write a structured research report in Markdown based strictly on the "
            "materials below. Structure: # Title, ## Summary, ## Findings (grouped "
            "by theme, citing source URLs inline), ## Sources (bullet list of "
            "URLs), ## Suggested next steps. Be thorough but do not fabricate "
            "content beyond the provided material.\n\n" + context
        )
        return await self._chat("workspace_report", [ChatMessage(role="user", content=prompt)])

    async def knowledge_map(self, workspace_id: str, user: User) -> dict:
        """Concept graph (nodes/edges) extracted from workspace materials."""
        context = await self._workspace_context(workspace_id, user)
        prompt = (
            "Extract a concept map from the research materials below. Respond with "
            "ONLY valid JSON matching this schema:\n"
            '{"nodes": [{"id": "string", "label": "string", "kind": "concept|source|question"}], '
            '"edges": [{"source": "node id", "target": "node id", "label": "string"}]}\n'
            "Limit to at most 20 nodes and 30 edges. Node ids must be short slugs.\n\n"
            + context
        )
        raw = await self._chat("knowledge_map", [ChatMessage(role="user", content=prompt)])
        data = _parse_json_object(raw)
        nodes = data.get("nodes") if isinstance(data, dict) else None
        edges = data.get("edges") if isinstance(data, dict) else None
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise AIUnavailableError("The model did not return a valid knowledge map.")
        node_ids = {n.get("id") for n in nodes if isinstance(n, dict) and n.get("id")}
        clean_edges = [
            e
            for e in edges
            if isinstance(e, dict) and e.get("source") in node_ids and e.get("target") in node_ids
        ]
        return {"nodes": nodes[:20], "edges": clean_edges[:30]}

    # ------------------------------------------------------------------
    # Context assembly
    # ------------------------------------------------------------------

    async def _workspace_context(self, workspace_id: str, user: User) -> str:
        workspace = await WorkspaceService(self.db).get_owned(workspace_id, user)
        bookmarks = (
            await self.db.execute(
                select(Bookmark)
                .where(Bookmark.workspace_id == workspace.id)
                .order_by(Bookmark.created_at.desc())
                .limit(MAX_CONTEXT_BOOKMARKS)
            )
        ).scalars().all()
        notes = (
            await self.db.execute(
                select(Note)
                .options(selectinload(Note.tags))
                .where(Note.workspace_id == workspace.id)
                .order_by(Note.updated_at.desc())
                .limit(MAX_CONTEXT_NOTES)
            )
        ).scalars().all()
        searches = (
            await self.db.execute(
                select(SearchHistory)
                .where(SearchHistory.workspace_id == workspace.id)
                .order_by(SearchHistory.created_at.desc())
                .limit(20)
            )
        ).scalars().all()

        parts = [f"WORKSPACE: {workspace.name}"]
        if workspace.description:
            parts.append(f"DESCRIPTION: {workspace.description}")
        if searches:
            parts.append(
                "RECENT SEARCHES:\n" + "\n".join(f"- {s.query}" for s in searches)
            )
        if bookmarks:
            lines = []
            for b in bookmarks:
                line = f"- {b.title or b.url} <{b.url}>"
                if b.snippet:
                    line += f" — {b.snippet[:200]}"
                lines.append(line)
            parts.append("SAVED SOURCES:\n" + "\n".join(lines))
        if notes:
            blocks = []
            for n in notes:
                content = n.content_text or n.content
                blocks.append(f"### {n.title}\n{content[:MAX_NOTE_CHARS]}")
            parts.append("NOTES:\n" + "\n\n".join(blocks))
        if len(parts) <= 1:
            raise AIUnavailableError(
                "This workspace has no materials yet. Save results or write notes first."
            )
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Tolerant model-output parsing
# ---------------------------------------------------------------------------

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _extract_json_payload(raw: str) -> str:
    match = _JSON_BLOCK.search(raw)
    if match:
        return match.group(1)
    return raw.strip()


def _parse_string_array(raw: str) -> list[str]:
    payload = _extract_json_payload(raw)
    try:
        data = json.loads(payload)
        if isinstance(data, list):
            return [str(item) for item in data]
    except ValueError:
        pass
    # Fallback: bullet/numbered lines.
    lines = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-*0123456789.) ").strip().strip('"')
        if line and not line.startswith("```"):
            lines.append(line)
    return lines


def _parse_json_object(raw: str) -> dict:
    payload = _extract_json_payload(raw)
    try:
        data = json.loads(payload)
        return data if isinstance(data, dict) else {}
    except ValueError:
        # Last resort: outermost braces.
        start, end = payload.find("{"), payload.rfind("}")
        if 0 <= start < end:
            try:
                data = json.loads(payload[start : end + 1])
                return data if isinstance(data, dict) else {}
            except ValueError:
                return {}
        return {}
