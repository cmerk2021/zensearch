/** API types mirroring the backend schemas. */

export interface User {
  id: string;
  username: string;
  email: string | null;
  display_name: string;
  role: "admin" | "user" | "readonly";
  is_active: boolean;
  ai_enabled: boolean;
  auth_source: string;
  created_at: string;
  last_login_at: string | null;
}

export interface Preferences {
  theme: "system" | "light" | "dark" | "amoled";
  accent: string;
  default_mode: SearchMode;
  default_profile_id: string | null;
  open_links_new_tab: boolean;
  keyboard_shortcuts: Record<string, string>;
  dashboard_layout: Record<string, unknown>;
  extra: Record<string, unknown>;
}

export type SearchMode = "normal" | "privacy" | "focus" | "research";

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  domain: string;
  favicon_url: string;
  providers: string[];
  positions: Record<string, number>;
  score: number;
  result_type: string;
  published_at: string | null;
  thumbnail: string | null;
  pinned: boolean;
}

export interface ProviderStatus {
  slug: string;
  name: string;
  ok: boolean;
  result_count: number;
  duration_ms: number;
  error: string | null;
  skipped: boolean;
  skip_reason: string | null;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  page: number;
  results: SearchResult[];
  providers: ProviderStatus[];
  duration_ms: number;
  cached: boolean;
  redirect: string | null;
  profile_slug: string | null;
  workspace_id: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  status: "active" | "archived";
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Tag {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  color: string;
}

export interface Bookmark {
  id: string;
  url: string;
  domain: string;
  title: string;
  description: string;
  snippet: string;
  favicon_url: string;
  workspace_id: string | null;
  source_provider: string | null;
  source_query: string | null;
  is_favorite: boolean;
  is_archived: boolean;
  tags: Tag[];
  created_at: string;
  updated_at: string;
}

export interface Collection {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  color: string;
  is_smart: boolean;
  rules: Record<string, unknown>;
  position: number;
  created_at: string;
}

export interface NoteLink {
  id: string;
  target_type: "note" | "bookmark";
  target_id: string;
}

export interface Note {
  id: string;
  title: string;
  content: string;
  workspace_id: string | null;
  is_pinned: boolean;
  tags: Tag[];
  links: NoteLink[];
  created_at: string;
  updated_at: string;
}

export interface NoteListItem {
  id: string;
  title: string;
  workspace_id: string | null;
  is_pinned: boolean;
  tags: Tag[];
  created_at: string;
  updated_at: string;
}

export interface SearchProfile {
  id: string;
  slug: string;
  name: string;
  description: string;
  icon: string;
  providers: string[];
  ranking: Record<string, unknown>;
  filters: Record<string, unknown>;
  ai: Record<string, unknown>;
  workspace: Record<string, unknown>;
  ui: Record<string, unknown>;
  is_default: boolean;
  is_active: boolean;
  position: number;
}

export interface HistoryEntry {
  id: string;
  query: string;
  mode: SearchMode;
  workspace_id: string | null;
  profile_id: string | null;
  providers: string[];
  result_count: number;
  duration_ms: number;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface InstanceInfo {
  name: string;
  tagline: string;
  logo_url: string;
  version: string;
  default_theme: string;
  ai_enabled: boolean;
  bootstrap_required: boolean;
}

export interface AuthMethods {
  local: boolean;
  registration: "open" | "closed";
  oidc: boolean;
  oidc_provider_name: string;
  ldap: boolean;
}

export interface ProviderConfig {
  slug: string;
  name: string;
  description: string;
  category: string;
  requires_api_key: boolean;
  enabled: boolean;
  weight: number;
  timeout_seconds: number | null;
  has_api_key: boolean;
  supports_paging: boolean;
  builtin: boolean;
}

export interface ProviderHealth {
  slug: string;
  state: "closed" | "open" | "half-open";
  success_rate: number;
  consecutive_failures: number;
  total_ok: number;
  total_fail: number;
  latency_ms_avg: number;
  last_error: string;
}

export interface PluginInfo {
  id: string;
  slug: string;
  name: string;
  version: string;
  description: string;
  author: string;
  license: string;
  homepage: string;
  types: string[];
  source_repo: string | null;
  status: "enabled" | "disabled" | "error";
  error: string;
  previous_version: string | null;
  installed_at: string;
  updated_at: string;
}

export interface Repository {
  id: string;
  name: string;
  url: string;
  kind: "official" | "community" | "private";
  enabled: boolean;
  last_synced_at: string | null;
  added_at: string;
}

export interface DomainRule {
  id: string;
  domain: string;
  action: "boost" | "lower" | "pin" | "block";
  weight: number;
  scope: "instance" | "profile" | "user";
  profile_id: string | null;
  user_id: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  actor_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  data: Record<string, unknown>;
  ip_address: string;
  created_at: string;
}

export interface UserSession {
  id: string;
  user_agent: string;
  ip_address: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
}
