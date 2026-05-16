# Frontend Audit Report

**Date:** 2026-05-16  
**Branch:** `front-end-dev`  
**Scope:** `src/app/(app)/`, `src/lib/`, `src/components/`  
**Modified files in scope:** `edit/[slug]/page.tsx`, `wiki/[slug]/page.tsx`, `review/page.tsx`

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 4 |
| Medium | 7 |
| Low / UX | 4 |
| Minor | 4 |
| **Total** | **22** |

---

## Critical

### C-1 — `publishMutation` non-null asserts a nullable field

**File:** `wiki/[slug]/page.tsx:62`

```typescript
{ revision_id: data!.page.current_draft_revision_id!, ... }
```

`current_draft_revision_id` is typed `string | null`. The `!` assertion is not guarded: if an editor clicks Publish on a page that has no pending draft (only a published revision), the call goes out with `revision_id: null`. The API will either reject it or publish the wrong thing. The Publish button should be disabled whenever `current_draft_revision_id` is null.

---

### C-2 — No error or loading state on the edit page for existing pages

**File:** `edit/[slug]/page.tsx:42-46`

```typescript
const { data } = useQuery({ ... });  // isLoading and error are ignored
```

When loading an existing page, the form renders immediately with empty `title`, `summary`, and `md`. If the fetch fails (404, network error, 403), there is no error message — the form stays blank. A user can then click "Save draft" and send an empty revision over their real content. There's also no loading skeleton, so fields flash from empty to populated.

---

### C-3 — `classifications` type mismatch causes broken rendering

**File:** `lib/api/types.ts:15`, `wiki/[slug]/page.tsx:267`

```typescript
// types.ts
classifications: string[];

// wiki/[slug]/page.tsx — treated as a Record
Object.entries(page.classifications ?? {}).map(([k, v]) => (
  <dt>{k}</dt><dd>{v}</dd>
))
```

`Object.entries` on a `string[]` produces numeric index keys (`"0"`, `"1"`, …). The dossier sidebar will render `0: Anomaly Class-A` instead of `Type: Anomaly Class-A`. Either the backend returns an object and the type is wrong, or the rendering code is wrong. The type should likely be `Record<string, string>`.

---

## High

### H-1 — Inserted image URLs are presigned and will expire

**File:** `edit/[slug]/page.tsx:109-110`

```typescript
const { url } = await mediaApi.getDownloadUrl(asset.id, token);
const snippet = `![${asset.filename}](${url})`;
```

The presigned URL returned by `/media/{id}/download-url` is embedded directly into the markdown source. These URLs expire (typical presigned URL TTL is minutes to hours). After expiry, all images inserted this way will become broken `<img>` tags.

The wiki page's `resolveMarkdownImageSrc` function attempts to rewrite image URLs, but its regex (`/\/(?:anomaly-media\/)?assets\/([0-9a-f-]{36})\//i`) targets a storage path pattern, not an expiring presigned URL. For the rewrite to work, the editor should insert a stable path (e.g., `![name](/media/{id})`) rather than a presigned URL.

---

### H-2 — Table of Contents anchor links are non-functional

**File:** `wiki/[slug]/page.tsx:256-262`

```typescript
.filter((l) => l.startsWith("## "))
.map((h) => (
  <a href={`#${h.toLowerCase().replace(/\s+/g, "-")}`}>{h}</a>
))
```

`ReactMarkdown` does not add `id` attributes to heading elements by default (that requires the `rehype-slug` plugin). There are no matching anchors in the DOM. Every ToC link navigates to a fragment that does not exist.

---

### H-3 — `generateDiff` only inspects the first 10 lines of each revision

**File:** `wiki/[slug]/page.tsx:322-337`

```typescript
const oldLines = oldText.split("\n").slice(0, 10);
const newLines = newText.split("\n").slice(0, 10);
// ...
for (let i = 0; i < Math.min(maxLen, 12); i++) {
```

The diff is doubly capped — first at 10 lines per side, then at 12 iterations. Any change beyond line 10 is invisible. For any article longer than a few sentences this produces a misleading "no diff" display. This is a placeholder implementation that has not been replaced.

---

### H-4 — Revision order assumed but never verified or sorted

**File:** `wiki/[slug]/page.tsx:284-286`

```typescript
const latest = revisions[0];
const prev   = revisions[1];
```

`revisions[0]` is treated as the newest entry. If the API returns revisions oldest-first (insertion order), the diff compares the wrong pair and the history list labels are inverted. The array should be explicitly sorted by `created_at` descending before indexing.

---

## Medium

### M-1 — `submitMutation` can use a stale page version immediately after a save

**File:** `edit/[slug]/page.tsx:180-190`

After a draft is saved, `qc.invalidateQueries` triggers a background refetch. If the user clicks "Submit for review" before the refetch resolves, `page!.version` is still the pre-save value and the transition request will receive a stale `expected_page_version`, producing a 409 conflict error on an action the user has every right to perform.

---

### M-2 — `handleSave` calls `markDirty()` right before saving

**File:** `edit/[slug]/page.tsx:192`

```typescript
const handleSave = () => { markDirty(); draftMutation.mutate(); };
```

`markDirty` is already called from the textarea's `onChange`. Calling it again here is semantically wrong: if the save mutation fails for a non-conflict reason, `isDirty` gets set to `true` even though the user has not made any new changes since the last successful save, incorrectly signalling unsaved work.

---

### M-3 — Reload after conflict silently discards local edits

**File:** `edit/[slug]/page.tsx:341-348`

When the user resolves a conflict by clicking "Reload latest", the query is invalidated and refetched. The `useEffect` on `data` then overwrites all local form state (title, summary, md) with server values. The user's in-progress edits are discarded with no warning. A confirmation dialog or a "your changes will be discarded" message is needed.

---

### M-4 — Token expiry not rechecked mid-session; no 401 auto-logout

**Files:** `lib/store/auth.ts:33-35`, `lib/api/client.ts:21-24`

Token expiry is validated only at login and at `hydrate()` (page load). If a user stays on the page past the token's `exp`, all subsequent API calls return 401, which the `request` wrapper converts to a generic `ApiError`. There is no middleware or interceptor to catch 401s and redirect to `/login`. The user sees opaque error states instead of a re-authentication prompt.

---

### M-5 — Edit and Submit actions visible to all Researchers regardless of authorship

**File:** `wiki/[slug]/page.tsx:141-153`

```typescript
{user && hasRole(user.role, "Researcher") && (
  <Link href={`/edit/${page.slug}`}>Edit</Link>
)}
{user && hasRole(user.role, "Researcher") && page.status === "Draft" && (
  <button onClick={() => submitMutation.mutate()}>Submit</button>
)}
```

Any Researcher can see the Edit link and Submit button on any page, regardless of authorship. Any Researcher can also submit another author's draft. The API may enforce ownership server-side, but users clicking these controls will receive surprising errors. The UI should check `page author == current user` before showing these controls, or the backend must be clear about multi-author intent.

---

### M-6 — Bottom-of-article "Edit page" link visible to Editors

**File:** `wiki/[slug]/page.tsx:245-249`

```typescript
{userRole && userRole !== "Public" && (
  <Link href={`/edit/${slug}`}>Edit page</Link>
)}
```

This shows the edit link to Editors (and Admins), which is inconsistent with the dossier's `hasRole(user.role, "Researcher")` check. Editors landing on the edit page would be allowed in by `AuthGuard` (which requires `minRole="Researcher"`, and Editor satisfies that), but the UI intent appears to limit editing to Researchers.

---

### M-7 — YAML frontmatter in RawTab not escaped; special characters break output

**File:** `wiki/[slug]/page.tsx:397-410`

```typescript
const frontmatter = `---
slug: ${page.slug}
tags:
${page.tags.map((t) => `  - ${t}`).join("\n")}
---`;
```

Slugs, types, or tags containing `:`, `#`, `"`, `\n`, or `[` produce invalid YAML. A tag like `zone: abandoned` becomes an inline mapping in the YAML list. The generated source will not parse correctly. Values should be quoted or the YAML should be built with a proper serializer.

---

## Low / UX

### L-1 — "Preview as Public" button is a dead stub

**File:** `edit/[slug]/page.tsx:419`

```typescript
<button className="btn btn--ghost btn--sm">Preview as Public</button>
```

No `onClick` handler. The button renders, does nothing when clicked, and misleads users into expecting a preview mode.

---

### L-2 — Discussion tab renders a non-functional comment form

**File:** `wiki/[slug]/page.tsx:374-391`

The "Add comment" section has an uncontrolled textarea and a "Post comment" button with no `onClick`. Users can type into the box but nothing is submitted. The UI implies the feature works when it does not. It should either be hidden behind a feature flag or replaced with a "coming soon" notice.

---

### L-3 — Review queue "Open" button uses a check icon

**File:** `review/page.tsx:69-74`

```typescript
<button ...><Icon name="check" size={11} /> Open</button>
```

The checkmark icon conventionally means "approve" or "confirm". Using it on a navigation button labelled "Open" creates a misleading affordance — an editor may expect it to approve the record directly.

---

### L-4 — No direct Publish action from the review queue

**File:** `review/page.tsx`

The editor workflow requires: queue → open wiki page → find Publish button in the dossier. There is no in-queue publish action. For a content moderation workflow this is an unnecessary number of steps and will slow down editorial throughput.

---

## Minor

### Mi-1 — Incorrect ESLint disable comment

**File:** `edit/[slug]/page.tsx:69`

```typescript
// eslint-disable-next-line react-hooks/set-state-in-effect
```

`react-hooks/set-state-in-effect` is not a real ESLint rule. The comment suppresses nothing. If this was intended to silence `react-hooks/exhaustive-deps`, it does not.

---

### Mi-2 — Media asset loading uses N+1 API calls

**File:** `wiki/[slug]/page.tsx:340-346`

```typescript
queryFn: () => pagesApi.getById(pageId, token ?? undefined)
  .then((state) => Promise.all(
    state.page.media_asset_ids.map((assetId) => mediaApi.getAsset(assetId, token!)),
  )),
```

One request fetches the page (which is already loaded in the parent), then N parallel requests fetch individual assets. For pages with many assets this creates a waterfall. A dedicated `GET /pages/{id}/media` endpoint returning all assets in one call would be cleaner.

---

### Mi-3 — `mediaApi.upload` throws plain `Error`, rest of API throws `ApiError`

**File:** `lib/api/media.ts:16-24`

The upload function bypasses the `request` wrapper and throws a plain `Error` instead of `ApiError`. Error handling at call sites must deal with two different error types. Consistent use of `ApiError` would allow status-code-aware handling (e.g., 413 Payload Too Large vs. 401).

---

### Mi-4 — `token!` non-null assertion relies on query `enabled` guard invisibly

**File:** `wiki/[slug]/page.tsx:344`

```typescript
enabled: !!token,
queryFn: () => ... mediaApi.getAsset(assetId, token!),
```

The `!` is only safe because of the `enabled` guard. TypeScript cannot verify this linkage. If someone removes or changes the `enabled` condition, the assertion becomes a runtime error. A local `if (!token) return []` inside the queryFn would be explicit and safe.

---

*Generated by manual audit — DoktorTomato / anomaly-wiki frontend*
