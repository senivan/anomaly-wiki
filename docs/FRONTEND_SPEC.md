# Frontend Specification — anomaly-wiki

> Status: Design spec. No frontend implementation exists yet.  
> Last updated: 2026-05-05

---

## 1. Overview

The frontend is a single web application serving two distinct audiences:

- **Public readers** — browse published encyclopedia entries, run searches. No account required.
- **Authenticated researchers/editors/admins** — manage drafts, submit revisions for review, publish, revert, upload media. Require a JWT issued by `researcher-auth-service`.

All frontend requests go exclusively through the `api-gateway`. The frontend never calls internal services directly.

---

## 2. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Framework | **Next.js 15 (App Router)** | SSR for public pages (SEO for encyclopedia entries), CSR for editor tools. One framework covers both audiences. |
| Language | **TypeScript** | Type contracts mirror `shared/models.py`; catches mismatches at compile time. |
| Server state | **TanStack Query v5** | Caching, background refetch, and mutation state for API calls. Avoids manual loading/error management. |
| Client state | **Zustand** | Auth token, current user identity, and UI state (modals, notifications). |
| Styling | **Tailwind CSS v4** | Utility-first; fast to prototype; no runtime overhead. |
| Markdown render | **react-markdown + remark-gfm** | Render stored Markdown content in read view. |
| Markdown edit | **CodeMirror 6** | Full-featured editor with syntax highlighting for Markdown. Lightweight and embeddable. |
| Forms | **React Hook Form + Zod** | Form state + schema validation aligned to API request shapes. |
| Dates | **date-fns** | Format revision timestamps, status change dates. |

### Rendering strategy per route

| Route category | Strategy | Why |
|---|---|---|
| Public encyclopedia entries (`/wiki/[slug]`) | SSR (Server Component) | Crawlable, no flash of loading state |
| Search results (`/search`) | SSR + client-side re-fetch on filter change | Initial render indexed; subsequent filters via client query |
| Editor workspace, revision history | CSR (Client Component) | Auth-gated, no SEO value, complex interactivity |
| Login / Register | CSR | No server context needed |

---

## 3. Route Map

| Path | Page | Min Role | Notes |
|---|---|---|---|
| `/` | Home | Public | Featured published entries, search bar, entry counts by type |
| `/search` | Search results | Public | Filters by type, tags; auth-aware (hides Internal for Public) |
| `/wiki/[slug]` | Encyclopedia entry (read) | Public | Shows published revision; Internal entries require auth |
| `/wiki/[slug]/history` | Revision history | Researcher | List of revisions; links to individual diffs |
| `/wiki/[slug]/history/[revisionId]` | Revision detail | Researcher | Full content + lineage |
| `/wiki/[slug]/edit` | Draft editor | Researcher | Create/update draft revision; metadata panel |
| `/wiki/new` | New entry form | Researcher | Create page + initial revision |
| `/workspace` | Editor workspace | Researcher | Pages the user has drafts on; status board |
| `/workspace/review` | Review queue | Editor | Pages in `Review` state; publish/reject controls |
| `/login` | Login | Public | Redirects to `/workspace` on success |
| `/register` | Register | Public | Creates `Researcher` role account |

### URL structure note

Current encyclopedia-service API routes use **UUIDs** (`/pages/{page_id}`). The frontend uses **slugs** in URLs for human-readability. A slug → ID resolution endpoint is required at the gateway (see [Section 9 — Required API Additions](#9-required-api-additions)).

---

## 4. Application Shell

```
<RootLayout>
  ├── <TopNav>               — logo, search input, auth state (login btn / username + role badge), mobile menu
  ├── <Toaster>              — global toast notifications (success, error, conflict)
  └── {children}             — page content
        <PageLayout>         — used by most routes
          ├── <Sidebar>      — on entry read view: type filter, related pages, tags
          └── <main>         — page-specific content
```

`<TopNav>` is always rendered. `<Sidebar>` is opt-in per route via layout composition.

---

## 5. Page-Level Component Trees

### `/wiki/[slug]` — Encyclopedia Entry (Read)

```
<EntryPage>
  ├── <EntryHeader>
  │     ├── <TypeBadge>          — e.g. "Anomaly", "Artifact" (colored chip)
  │     ├── <StatusBadge>        — shown only to Researcher+; e.g. "Published"
  │     ├── <VisibilityBadge>    — shown only to Researcher+; "Internal" warning
  │     └── <EntryActions>       — Edit button (Researcher+), Status controls (Editor+)
  ├── <EntryContent>             — react-markdown render of revision.content
  ├── <EntryMeta>
  │     ├── <TagList>            — tags from page metadata
  │     ├── <ClassificationList> — classifications
  │     └── <LastUpdated>        — revision.created_at, author_id
  ├── <RelatedPages>             — links derived from page relationships
  └── <MediaGallery>             — images/documents attached via media references
```

### `/wiki/[slug]/edit` — Draft Editor

```
<EditorPage>
  ├── <EditorToolbar>
  │     ├── <SaveDraftButton>      — POST /pages/{id}/drafts
  │     ├── <SubmitForReviewButton>— POST /pages/{id}/status → Review (Researcher)
  │     ├── <PublishButton>        — POST /pages/{id}/publish (Editor+)
  │     └── <RevertButton>         — POST /pages/{id}/revert (Editor+)
  ├── <EditorMain>
  │     ├── <TitleInput>
  │     ├── <SummaryInput>
  │     └── <MarkdownEditor>       — CodeMirror 6
  ├── <MetadataPanel>              — collapsible sidebar
  │     ├── <TagEditor>
  │     ├── <ClassificationEditor>
  │     ├── <RelatedPagesSelector> — search-based multi-select
  │     └── <MediaAttachments>     — upload + reference manager
  └── <VersionConflictModal>       — shown on 409; prompts refresh or force-save
```

### `/wiki/[slug]/history` — Revision History

```
<HistoryPage>
  ├── <RevisionTimeline>
  │     └── <RevisionRow> ×N
  │           ├── revision ID (short), author, timestamp, summary
  │           ├── <RevertButton> (Editor+)
  │           └── link → /history/{revisionId}
  └── <PublishedRevisionBanner>   — highlights which revision is currently published
```

### `/workspace` — Editor Workspace

```
<WorkspacePage>
  ├── <WorkspaceHeader>            — "Your drafts" title, "New entry" button
  └── <StatusBoard>
        ├── <DraftColumn>
        │     └── <PageCard> ×N   — slug, title, type, last modified, Edit link
        └── <ReviewColumn> (Editor+)
              └── <PageCard> ×N   — with Publish / Reject actions
```

### `/search` — Search Results

```
<SearchPage>
  ├── <SearchBar>                  — text input, debounced autocomplete
  ├── <FilterRow>
  │     ├── <TypeFilterChips>      — Article | Anomaly | Artifact | Location | …
  │     └── <VisibilityToggle>     — Public / All (Researcher+ only)
  └── <SearchResultList>
        └── <SearchResultCard> ×N
              ├── <TypeBadge>
              ├── title + slug link
              └── snippet (highlighted)
```

---

## 6. Communication Layer

### 6.1 Directory Structure

```
src/lib/api/
  client.ts       — base fetch wrapper; attaches auth header, parses errors
  types.ts        — TypeScript contracts (mirrors shared/models.py)
  errors.ts       — typed API error classes
  auth.ts         — /auth/* calls
  pages.ts        — /pages/* calls
  search.ts       — /search/* calls
  media.ts        — /media/* calls
```

All modules export plain async functions. TanStack Query `useQuery` / `useMutation` hooks wrap these functions at the component layer — the API modules themselves have no React dependency.

### 6.2 Base Client

```typescript
// src/lib/api/client.ts

const GATEWAY = process.env.NEXT_PUBLIC_GATEWAY_URL;   // e.g. http://localhost:8000

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${GATEWAY}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? "Unknown error", body);
  }

  return res.json() as Promise<T>;
}
```

`ApiError` carries `status: number` and `detail: string`. Callers pattern-match on status to drive UI (see error table below).

### 6.3 TypeScript Type Contracts

These mirror `shared/models.py` and the encyclopedia-service domain models exactly. Any divergence is a bug.

```typescript
// src/lib/api/types.ts

export type PageType =
  | "Article" | "Anomaly" | "Artifact" | "Location"
  | "Incident" | "Expedition" | "Researcher Note";

export type PageStatus = "Draft" | "Review" | "Published" | "Archived" | "Redacted";

export type Visibility = "Public" | "Internal";

export type UserRole = "Public" | "Researcher" | "Editor" | "Admin";

export interface Page {
  id: string;                            // UUID
  slug: string;
  type: PageType;
  status: PageStatus;
  visibility: Visibility;
  current_published_revision_id: string | null;
  current_draft_revision_id: string | null;
  version: number;                       // optimistic lock counter
  tags: string[];
  classifications: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface Revision {
  id: string;
  page_id: string;
  parent_revision_id: string | null;
  author_id: string | null;
  title: string;
  summary: string;
  content: string;                       // Markdown
  created_at: string;
}

export interface RevisionLineage {
  revision: Revision;
  lineage: Revision[];                   // ancestors, oldest last
}

export interface PageState {
  page: Page;
  draft_revision: Revision | null;
  published_revision: Revision | null;
}

export interface MediaAsset {
  id: string;
  filename: string;
  mime_type: string;
  uploaded_by: string;
  size_bytes: number;
  created_at: string;
}

export interface SearchResult {
  page_id: string;
  slug: string;
  title: string;
  type: PageType;
  snippet: string;
  tags: string[];
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
}

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
}

export interface CurrentUser {
  id: string;
  email: string;
  role: UserRole;
}
```

### 6.4 Service Modules

```typescript
// src/lib/api/pages.ts (representative subset)

export const pagesApi = {
  getBySlug: (slug: string, token?: string) =>
    request<PageState>(`/pages/slug/${slug}`, { token }),

  getById: (pageId: string, token?: string) =>
    request<PageState>(`/pages/${pageId}`, { token }),

  create: (body: CreatePageRequest, token: string) =>
    request<PageState>(`/pages`, { method: "POST", body: JSON.stringify(body), token }),

  createDraft: (pageId: string, body: CreateDraftRequest, token: string) =>
    request<Revision>(`/pages/${pageId}/drafts`, { method: "POST", body: JSON.stringify(body), token }),

  updateMetadata: (pageId: string, body: UpdateMetadataRequest, token: string) =>
    request<Page>(`/pages/${pageId}/metadata`, { method: "PUT", body: JSON.stringify(body), token }),

  publish: (pageId: string, body: PublishRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/publish`, { method: "POST", body: JSON.stringify(body), token }),

  revert: (pageId: string, body: RevertRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/revert`, { method: "POST", body: JSON.stringify(body), token }),

  transitionStatus: (pageId: string, body: StatusTransitionRequest, token: string) =>
    request<PageState>(`/pages/${pageId}/status`, { method: "POST", body: JSON.stringify(body), token }),

  listRevisions: (pageId: string, token?: string) =>
    request<Revision[]>(`/pages/${pageId}/revisions`, { token }),

  getRevision: (pageId: string, revisionId: string, token?: string) =>
    request<RevisionLineage>(`/pages/${pageId}/revisions/${revisionId}`, { token }),
};
```

```typescript
// src/lib/api/auth.ts

export const authApi = {
  login: (email: string, password: string) =>
    request<AuthToken>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: email, password }),
    }),

  register: (email: string, password: string) =>
    request<CurrentUser>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: (token: string) =>
    request<void>("/auth/logout", { method: "POST", token }),
};
```

### 6.5 Auth Token Management

```
Storage: localStorage (key: "anomaly_wiki_token")
Runtime: Zustand auth store (in-memory, survives client navigation)

Lifecycle:
  App boot   → read localStorage → populate Zustand if token present and not expired
  Login      → store token in Zustand + localStorage
  Logout     → clear both; redirect to /
  401 from API → clear token; redirect to /login with ?redirect=<current path>
  
Token format: RS256 JWT issued by researcher-auth-service
  Relevant claims: sub (user_id), role, exp
  Frontend decodes claims client-side (jwt-decode) for role checks; 
  never trusts decoded role for server-side access — backend enforces.
```

### 6.6 Error Handling Matrix

| HTTP Status | Cause | Frontend Behavior |
|---|---|---|
| 400 | Validation error | Show inline field errors from `detail` |
| 401 | Missing or expired token | Clear token, redirect to `/login?redirect=...` |
| 403 | Insufficient role | Show "Access denied" inline message |
| 404 | Page/revision not found | Render 404 page |
| 409 | Optimistic lock conflict (`StalePageVersionError`) | Show `<VersionConflictModal>` — user chooses "Reload latest" or "Force save" |
| 422 | Unprocessable entity | Show validation errors |
| 5xx | Gateway or service error | Global toast "Something went wrong, try again" |

### 6.7 Optimistic Locking on the Frontend

Every mutation that modifies page state requires the current `page.version` as `expected_page_version` in the request body. The frontend must:

1. Always fetch `PageState` before editing — store `page.version` in the editor state.
2. On save/publish/revert: include `expected_page_version: page.version`.
3. On 409 response: show `<VersionConflictModal>` offering:
   - **Reload latest** — re-fetch `PageState`, discard local edits (or show diff)
   - **Force save** — re-fetch latest version, auto-increment `expected_page_version` to match, re-submit (Editor+ only)

```typescript
// How expected_page_version flows in a draft save
const { page } = usePageState(slug);           // version: 7

await pagesApi.createDraft(page.id, {
  parent_revision_id: page.current_draft_revision_id,
  title,
  summary,
  content,
  expected_page_version: page.version,         // pass 7; 409 if it changed
}, token);
```

---

## 7. State Management

### Auth store (Zustand)

```typescript
interface AuthState {
  token: string | null;
  user: CurrentUser | null;         // decoded from JWT
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}
```

Persisted to `localStorage` on every write.

### Editor store (Zustand)

```typescript
interface EditorState {
  pageId: string | null;
  pageVersion: number | null;       // optimistic lock baseline
  isDirty: boolean;                 // unsaved local changes
  setBaseline: (page: Page) => void;
  markDirty: () => void;
  reset: () => void;
}
```

Reset on route change. Used to warn "You have unsaved changes" before navigation.

### Server state (TanStack Query)

| Query key | Data | Stale time |
|---|---|---|
| `["page", slug]` | `PageState` | 60s for public, 0 for editor view |
| `["revisions", pageId]` | `Revision[]` | 30s |
| `["revision", pageId, revId]` | `RevisionLineage` | ∞ (immutable) |
| `["search", query, filters]` | `SearchResponse` | 30s |
| `["media", assetId]` | `MediaAsset` | 5m |

---

## 8. Role-Based Access Control

### What each role can do

| Action | Public | Researcher | Editor | Admin |
|---|---|---|---|---|
| Read published Public entries | ✓ | ✓ | ✓ | ✓ |
| Read published Internal entries | — | ✓ | ✓ | ✓ |
| Read draft revisions | — | own only | ✓ | ✓ |
| View revision history | — | ✓ | ✓ | ✓ |
| Create new page | — | ✓ | ✓ | ✓ |
| Create draft revision | — | ✓ | ✓ | ✓ |
| Submit for Review (status Draft→Review) | — | ✓ | ✓ | ✓ |
| Publish revision | — | — | ✓ | ✓ |
| Revert to past revision | — | — | ✓ | ✓ |
| Archive / Redact | — | — | — | ✓ |
| Update metadata | — | ✓ | ✓ | ✓ |
| Upload media | — | ✓ | ✓ | ✓ |
| View Internal search results | — | ✓ | ✓ | ✓ |
| Review queue access | — | — | ✓ | ✓ |

### Frontend enforcement

Role checks gate **rendering** of action controls (buttons, links, forms). The actual enforcement happens in the backend. Frontend role checks use the decoded JWT `role` claim from Zustand auth store.

```typescript
// Example: hide Edit button for Public role
const { user } = useAuthStore();
const canEdit = user && user.role !== "Public";
```

Protected routes redirect to `/login` if `token` is absent:

```typescript
// src/components/AuthGuard.tsx
// Wrap any route that requires authentication
export function AuthGuard({ minRole, children }: AuthGuardProps) {
  const { user } = useAuthStore();
  if (!user) return <redirect to={`/login?redirect=${path}`} />;
  if (!hasRole(user.role, minRole)) return <AccessDenied />;
  return children;
}

const ROLE_RANK: Record<UserRole, number> = {
  Public: 0, Researcher: 1, Editor: 2, Admin: 3,
};
function hasRole(actual: UserRole, required: UserRole) {
  return ROLE_RANK[actual] >= ROLE_RANK[required];
}
```

---

## 9. Required API Additions

These gaps exist between what the current API gateway exposes and what the frontend needs. They must be added before or alongside frontend implementation.

| # | Endpoint | Why needed |
|---|---|---|
| 1 | `GET /pages/slug/{slug}` | Frontend URLs use human-readable slugs; gateway currently only routes by UUID. Without this, slug → ID resolution is impossible without a search hack. |
| 2 | `GET /auth/me` | Fetch current user identity (id, email, role) from a valid JWT. The decoded JWT carries `role` but `email` and display name need a server source. |
| 3 | `GET /search?q=...&type=...&visibility=...` | Search service is a stub. The gateway route exists but the service does nothing. Frontend search UI blocks on this. |
| 4 | `GET /search/suggest?q=...` | Autocomplete in `<SearchBar>`. Also depends on search service. |

Gap 1 is blocking for the encyclopedia read view. Gaps 3–4 are blocking for search. Gap 2 is optional (can skip if JWT claims suffice).

---

## 10. Environment Configuration

```
# .env.local (frontend)
NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000

# For server-side fetch in Next.js Server Components (internal network)
GATEWAY_INTERNAL_URL=http://api-gateway:8000
```

Server Components use `GATEWAY_INTERNAL_URL` (container-to-container, faster, no CORS). Client Components use `NEXT_PUBLIC_GATEWAY_URL` (browser → gateway).

---

## 11. Key Data Flows

### Login flow
```
User submits /login form
  → authApi.login(email, password)
  → POST /auth/login → JWT
  → authStore.login(token) [stores in Zustand + localStorage]
  → redirect to /workspace (or ?redirect param)
```

### Read a published encyclopedia entry
```
Browser navigates to /wiki/psy-dog
  → Next.js Server Component calls pagesApi.getBySlug("psy-dog")
    → GET /pages/slug/psy-dog (no auth header; public)
    → gateway → encyclopedia-service
    → returns PageState { page, published_revision, draft_revision: null }
  → render <EntryPage> with published_revision.content as Markdown
  → if visibility=Internal and no token in cookie → 401 → redirect /login
```

### Save a draft revision
```
Editor modifies content in <MarkdownEditor>
  → editorStore.markDirty()
  → clicks "Save draft"
  → pagesApi.createDraft(page.id, { title, summary, content, expected_page_version: page.version }, token)
    → POST /pages/{id}/drafts
    → 200: update TanStack Query cache, reset editorStore.isDirty
    → 409: show <VersionConflictModal>
    → 401: redirect to /login (token expired mid-session)
```

### Search flow
```
User types in <SearchBar>
  → debounced 300ms → searchApi.suggest(query)
    → GET /search/suggest?q=... → autocomplete dropdown
  → user submits
  → navigate to /search?q=psy+dog&type=Anomaly
    → Next.js SSR: searchApi.query({ q, type })
      → GET /search?q=psy+dog&type=Anomaly
      → returns SearchResponse { results, total }
    → render <SearchResultList>
  → user clicks result (has page_id + slug)
  → navigate to /wiki/{slug}
```
