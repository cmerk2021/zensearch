# ADR-0008: Unified knowledge object

**Status:** Accepted

## Context

The brief lists "bookmarks", "saved results", and "read later" as separate
concepts. Modeling them as separate tables triplicates tagging, collections,
search indexing, and export logic.

## Decision

One `bookmarks` table is the single knowledge object. A bookmark may carry
search provenance (`source_provider`, `source_query`, `snippet`) when created
via "save result", or none when created manually. "Read Later" is a default
collection, not a type. Notes link to bookmarks through `note_links`.

## Consequences

- Tags, collections, full-text search, exports and AI digests operate on one
  entity.
- The results-page "save" action and the bookmark composer share one API.
- Smart collections filter on provenance fields like any other field.
