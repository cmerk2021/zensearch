# Using Zen

## Search

Type in the box, press Enter. Press `/` anywhere to focus the search box,
`Ctrl/⌘ K` for the command palette.

### Search modes

| Mode | What it does |
|---|---|
| **Normal** | Standard search with history and personalization. |
| **Privacy** | Nothing recorded — no history, no personalization, no caching. The UI badges it clearly. |
| **Focus** | Removes social media, shopping, entertainment, and tabloid domains, and skips those provider categories entirely. |
| **Research** | Associates every search with a workspace and surfaces capture tools. |

Switch modes with the pills under the search box or from the command palette.

### Bangs

Jump straight to another site's search:

| Bang | Target |
|---|---|
| `!g` | Google |
| `!ddg` | DuckDuckGo |
| `!gh` | GitHub |
| `!so` | Stack Overflow |
| `!wiki` / `!w` | Wikipedia |
| `!yt` | YouTube |
| `!reddit` / `!r` | Reddit |
| `!mdn` | MDN Web Docs |
| `!npm`, `!pypi`, `!crates` | Package registries |
| `!hn` | Hacker News (Algolia) |
| `!aw` | Arch Wiki |
| `!dh` | Docker Hub |

`GET /api/v1/search/bangs` lists everything available on your instance —
admins can add custom bangs, and plugins can register more.

### Search profiles

Profiles are admin-curated presets (Engineering, Research, Homelab, Academic,
Privacy…) that change which providers run and how results are ranked. Pick one
from the dropdown next to the mode pills, or set a default in **Settings →
Search defaults**. Your choice syncs across devices.

### Result actions

Hover a result (or tap on mobile):

- **Save** — bookmark it, optionally straight into a workspace. Provenance
  (provider + query) is stored with it.
- **Cite** — copies `Title. URL (accessed date)` to the clipboard.
- **AI summary** — top of the page; summarizes the result set with citations
  (only when AI is enabled).

## Workspaces

A workspace is a persistent research context: its searches, saved sources,
and notes live together and can be exported as one bundle.

- Create from **Workspaces → New workspace** or the command palette.
- Search in **Research mode** with a workspace selected to log searches to it.
- **Export** produces a zip of Markdown notes + bookmarks + a JSON snapshot.
- **AI digest** (optional) writes an overview of everything collected.

## Bookmarks, collections, tags

- **Bookmarks** are the universal saved-source object. Deduplicated by URL —
  saving the same page twice updates the original.
- **Collections** group bookmarks. **Smart collections** populate themselves
  from rules (e.g. *domain contains github.com*).
- **Tags** are hierarchical (`linux/networking`) and shared between bookmarks
  and notes.

## Notes

Markdown notes with automatic revision history (restore any previous
version), pinning, workspace association, tagging, and links to bookmarks or
other notes. Notes autosave as you type.

## Keyboard shortcuts

| Key | Action |
|---|---|
| `/` | Focus search |
| `Ctrl/⌘ K` | Command palette |
| `↑` `↓` | Navigate suggestions |
| `Esc` | Close dialogs/suggestions |

## Your data

**Settings → Your data** exports everything you own as JSON. Bookmarks also
export as a standard Netscape HTML file importable by any browser.
