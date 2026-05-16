"use client";
import { Fragment, isValidElement, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { pagesApi } from "@/lib/api/pages";
import { mediaApi } from "@/lib/api/media";
import { useAuthStore, hasRole } from "@/lib/store/auth";
import { Icon } from "@/components/ui/Icon";
import { StatusPill } from "@/components/ui/StatusPill";
import { PageTypeChip } from "@/components/ui/PageTypeChip";
import { Stamp } from "@/components/ui/Stamp";
import Link from "next/link";
import type { Revision } from "@/lib/api/types";

type Tab = "article" | "revisions" | "media" | "discussion" | "raw";

const GATEWAY = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";

function extractAssetId(value: string): string | null {
  const match = value.match(
    /([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/i,
  );
  return match?.[1] ?? null;
}

function resolveMarkdownImageSrc(src: string | undefined, slug: string): string | undefined {
  if (!src) return src;
  try {
    const url = new URL(src, window.location.href);
    const assetId =
      extractAssetId(url.pathname) ??
      extractAssetId(url.search) ??
      extractAssetId(src);
    if (!assetId) return src;
    return `${GATEWAY}/pages/slug/${encodeURIComponent(slug)}/media/${assetId}/content`;
  } catch {
    return src;
  }
}

function normalizeClassifications(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .filter((entry): entry is string => typeof entry === "string")
      .map((entry) => entry.trim())
      .filter(Boolean);
  }

  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, entry]) => typeof entry === "string")
      .map(([key, entry]) => `${key}: ${String(entry).trim()}`)
      .filter(Boolean);
  }

  return [];
}

function textFromNode(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textFromNode).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textFromNode(node.props.children);
  return "";
}

function slugHeading(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "section";
}

function uniqueHeadingId(text: string, counts: Map<string, number>): string {
  const base = slugHeading(text);
  const count = counts.get(base) ?? 0;
  counts.set(base, count + 1);
  return count === 0 ? base : `${base}-${count + 1}`;
}

function articleHeadings(content: string): { id: string; text: string }[] {
  const counts = new Map<string, number>();
  return content
    .split("\n")
    .filter((line) => line.startsWith("## "))
    .map((line) => line.slice(3).trim())
    .filter(Boolean)
    .map((text) => ({ id: uniqueHeadingId(text, counts), text }));
}

function yamlScalar(value: string): string {
  return JSON.stringify(value);
}

function yamlList(values: string[]): string {
  if (values.length === 0) return "[]";
  return `\n${values.map((value) => `  - ${yamlScalar(value)}`).join("\n")}`;
}

export default function WikiPage() {
  const { slug } = useParams<{ slug: string }>();
  const { user, token } = useAuthStore();
  const [tab, setTab] = useState<Tab>("article");
  const qc = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["page", slug],
    queryFn: () => pagesApi.getBySlug(slug, token ?? undefined),
  });

  const { data: revisionsData } = useQuery({
    queryKey: ["revisions", data?.page.id],
    queryFn: () => pagesApi.listRevisions(data!.page.id, token ?? undefined),
    enabled: !!data && tab === "revisions",
  });

  const submitMutation = useMutation({
    mutationFn: () => pagesApi.transitionStatus(
      data!.page.id,
      { status: "Review", expected_page_version: data!.page.version },
      token!,
    ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["page", slug] }),
  });

  const publishMutation = useMutation({
    mutationFn: () => {
      const draftRevisionId = data?.page.current_draft_revision_id;
      if (!data || !draftRevisionId) {
        throw new Error("No draft revision available to publish.");
      }
      return pagesApi.publish(
        data.page.id,
        { revision_id: draftRevisionId, expected_page_version: data.page.version },
        token!,
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["page", slug] }),
  });

  if (isLoading) {
    return (
      <div>
        <div className="page-header">
          <div>
            <div className="kicker">Loading…</div>
            <div style={{ height: 48, background: "var(--paper-2)", margin: "12px 0", width: "60%" }} />
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="callout callout--danger" style={{ maxWidth: "none" }}>
        <div className="callout__title"><Icon name="alert" size={11} /> Error</div>
        <div>Page not found or access denied. <Link href="/">Return home</Link></div>
      </div>
    );
  }

  const { page, current_published_revision, current_draft_revision } = data;
  const revision = current_published_revision ?? current_draft_revision;
  const revisions = (revisionsData?.revisions ?? []) as Revision[];
  const canPublish = page.current_draft_revision_id !== null;
  const canEditDraft =
    user?.role === "Researcher" &&
    current_draft_revision?.author_id === user.id;

  const TABS: { id: Tab; label: string }[] = [
    { id: "article",   label: "Article" },
    { id: "revisions", label: "Revisions" },
    { id: "media",     label: "Media" },
    { id: "discussion",label: "Discussion" },
    { id: "raw",       label: "Raw markdown" },
  ];

  return (
    <div>
      <header className="page-header">
        <div>
          <div className="page-header__crumbs">
            <Link href="/" style={{ textDecoration: "none", color: "var(--ink-3)" }}>Wiki</Link>
            <span>/</span>
            <Link href={`/search?type=${page.type}`} style={{ textDecoration: "none", color: "var(--ink-3)" }}>{page.type}s</Link>
            <span>/</span>
            <span className="mono">{page.slug}</span>
          </div>
          <div className="row" style={{ gap: 10, marginBottom: 6 }}>
            <PageTypeChip type={page.type} />
            <StatusPill status={page.status} visibility={page.visibility} />
          </div>
          <h1>{revision?.title ?? page.slug}</h1>
          <div className="page-header__code">{page.slug}</div>
          <p className="page-header__sum">{revision?.summary}</p>
          <div className="page-header__chips">
            {page.tags.map((t) => (
              <span key={t} className="tag mono">#{t}</span>
            ))}
          </div>
        </div>

        <aside className="dossier">
          <div className="dossier__lab">
            <span>Dossier</span>
            <span>{page.slug}</span>
          </div>
          <dl>
            <dt>Type</dt>      <dd>{page.type}</dd>
            <dt>Status</dt>    <dd>{page.status}</dd>
            <dt>Visibility</dt><dd>{page.visibility}</dd>
            <dt>Tags</dt>      <dd>{page.tags.join(", ") || "—"}</dd>
            <dt>Created</dt>   <dd>{page.created_at.slice(0, 10)}</dd>
            <dt>Updated</dt>   <dd>{page.updated_at.slice(0, 10)}</dd>
          </dl>
          <div className="row" style={{ marginTop: 14, gap: 6, flexWrap: "wrap" }}>
            {canEditDraft && (
              <Link href={`/edit/${page.slug}`} className="btn btn--sm">
                <Icon name="edit" size={11} /> Edit
              </Link>
            )}
            {canEditDraft && page.status === "Draft" && (
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => submitMutation.mutate()}
                disabled={submitMutation.isPending}
              >
                <Icon name="check" size={11} /> Submit
              </button>
            )}
            {user && hasRole(user.role, "Editor") && page.status === "Review" && (
              <button
                className="btn btn--primary btn--sm"
                onClick={() => publishMutation.mutate()}
                disabled={publishMutation.isPending || !canPublish}
              >
                <Icon name="check" size={11} /> Publish
              </button>
            )}
          </div>
        </aside>
      </header>

      <div className="article-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`article-tab ${tab === t.id ? "is-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "article" && (
        <ArticleTab
          page={page}
          revision={revision}
          canEditDraft={canEditDraft}
          slug={slug}
        />
      )}
      {tab === "revisions" && <RevisionsTab revisions={revisions} />}
      {tab === "media"     && <MediaTab pageId={page.id} token={token} />}
      {tab === "discussion"&& <DiscussionTab />}
      {tab === "raw"       && <RawTab page={page} revision={revision} />}
    </div>
  );
}

function ArticleTab({ page, revision, canEditDraft, slug }: {
  page: import("@/lib/api/types").Page;
  revision: Revision | null | undefined;
  canEditDraft: boolean;
  slug: string;
}) {
  const classifications = normalizeClassifications(
    (page as { classifications?: unknown }).classifications,
  );
  const headings = articleHeadings(revision?.content ?? "");
  const renderedHeadingCounts = new Map<string, number>();

  return (
    <div className="article-grid">
      <div className="prose">
        {page.status === "Draft"  && (
          <div style={{ marginBottom: 16 }}><Stamp kind="draft" text="DRAFT — NOT PUBLISHED" /></div>
        )}
        {page.status === "Review" && (
          <div style={{ marginBottom: 16 }}><Stamp kind="approved" text="UNDER EDITOR REVIEW" /></div>
        )}
        {page.visibility === "Internal" && page.status === "Published" && (
          <div style={{ marginBottom: 16 }}><Stamp text="INTERNAL · L2+" /></div>
        )}

        {revision?.content ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h2: ({ children }) => (
                <h2 id={uniqueHeadingId(textFromNode(children), renderedHeadingCounts)}>
                  {children}
                </h2>
              ),
              table: ({ children }) => <table className="field-table">{children}</table>,
              img: ({ src, alt }) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={resolveMarkdownImageSrc(typeof src === "string" ? src : undefined, page.slug)}
                  alt={alt ?? ""}
                />
              ),
              blockquote: ({ children }) => (
                <div className="callout callout--info">
                  <div className="callout__title"><Icon name="shield" size={11} />Note</div>
                  <div>{children}</div>
                </div>
              ),
            }}
          >
            {revision.content}
          </ReactMarkdown>
        ) : (
          <p className="muted">No content available.</p>
        )}

        <hr style={{ border: 0, borderTop: "1px solid var(--rule)", margin: "32px 0 16px" }} />
        <div className="spread">
          <span className="mono xsmall muted">Last revision · {page.updated_at.slice(0, 10)}</span>
          {canEditDraft && (
            <Link href={`/edit/${slug}`} className="btn btn--sm">
              <Icon name="edit" size={11} /> Edit page
            </Link>
          )}
        </div>
      </div>

      <aside>
        <nav className="toc">
          <h6>On this page</h6>
          {headings.map((heading) => (
            <a key={heading.id} href={`#${heading.id}`}>{heading.text}</a>
          ))}
        </nav>
        <div style={{ marginTop: 32 }}>
          <h6 className="kicker" style={{ marginBottom: 8 }}>Classification</h6>
          <dl style={{ fontFamily: "JetBrains Mono", fontSize: 11, color: "var(--ink-2)" }}>
            {classifications.length === 0 && (
              <dd style={{ margin: "0 0 4px" }}>—</dd>
            )}
            {classifications.map((classification) => (
              <dd key={classification} style={{ margin: "0 0 4px" }}>{classification}</dd>
            ))}
            {Object.entries(page.classifications ?? {}).map(([k, v]) => (
              <Fragment key={k}>
                <dt style={{ color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.08em", fontSize: 10.5 }}>{k}</dt>
                <dd style={{ margin: 0 }}>{v}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      </aside>
    </div>
  );
}

function RevisionsTab({ revisions }: { revisions: Revision[] }) {
  if (revisions.length === 0) {
    return <div className="muted" style={{ padding: "20px 0" }}>No revision history available.</div>;
  }
  const sorted = [...revisions].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  const latest  = sorted[0];
  const prev    = sorted[1];
  const diffLines = generateDiff(prev?.content ?? "", latest?.content ?? "");

  return (
    <div className="article-grid" style={{ gridTemplateColumns: "1fr 320px" }}>
      <div>
        <div className="kicker" style={{ marginBottom: 10 }}>
          Diff · r{sorted.length} ↔ r{sorted.length - 1}
        </div>
        <div className="diff" style={{ marginBottom: 24 }}>
          {diffLines.map((line, i) => (
            <div key={i} className={`diff__row ${line.type}`}>
              <div className="diff__num">{line.num}</div>
              <div className="diff__line">{line.text}</div>
            </div>
          ))}
        </div>
      </div>
      <aside>
        <h6 className="kicker" style={{ marginBottom: 8 }}>Revision history</h6>
        <ul className="related-list">
          {sorted.map((r, i) => (
            <li key={r.id} style={{ display: "block" }}>
              <div className="spread">
                <b>r{sorted.length - i}</b>
                <span className="mono xsmall muted">{r.created_at.slice(0, 16)}</span>
              </div>
              <div className="xsmall" style={{ margin: "2px 0" }}>{r.summary || "No summary"}</div>
              <div className="mono xsmall muted">{r.author_id ?? "unknown"}</div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

type DiffLine = { type: "ctx" | "add" | "del"; num: number; text: string };

function generateDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const lengths = Array.from({ length: oldLines.length + 1 }, () =>
    Array<number>(newLines.length + 1).fill(0),
  );

  for (let i = oldLines.length - 1; i >= 0; i--) {
    for (let j = newLines.length - 1; j >= 0; j--) {
      lengths[i][j] = oldLines[i] === newLines[j]
        ? lengths[i + 1][j + 1] + 1
        : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
    }
  }

  const lines: DiffLine[] = [];
  let oldIndex = 0;
  let newIndex = 0;

  while (oldIndex < oldLines.length && newIndex < newLines.length) {
    const oldLine = oldLines[oldIndex];
    const newLine = newLines[newIndex];

    if (oldLine === newLine) {
      lines.push({ type: "ctx", num: newIndex + 1, text: newLine });
      oldIndex++;
      newIndex++;
    } else if (lengths[oldIndex + 1][newIndex] >= lengths[oldIndex][newIndex + 1]) {
      lines.push({ type: "del", num: oldIndex + 1, text: oldLine });
      oldIndex++;
    } else {
      lines.push({ type: "add", num: newIndex + 1, text: newLine });
      newIndex++;
    }
  }

  while (oldIndex < oldLines.length) {
    lines.push({ type: "del", num: oldIndex + 1, text: oldLines[oldIndex] });
    oldIndex++;
  }
  while (newIndex < newLines.length) {
    lines.push({ type: "add", num: newIndex + 1, text: newLines[newIndex] });
    newIndex++;
  }

  return lines;
}

function MediaTab({ pageId, token }: { pageId: string; token: string | null }) {
  const { data } = useQuery({
    queryKey: ["page-media", pageId],
    queryFn: async () => {
      if (!token) return [];
      const state = await pagesApi.getById(pageId, token);
      return Promise.all(
        state.page.media_asset_ids.map((assetId) => mediaApi.getAsset(assetId, token)),
      );
    },
    enabled: !!token,
  });

  const assets = data ?? [];

  return (
    <div className="muted" style={{ padding: "20px 0" }}>
      {!token && <span>Sign in to view attached media.</span>}
      {token && assets.length === 0 && <span>No media assets are linked to this record.</span>}
      {assets.length > 0 && (
        <div className="media-grid">
          {assets.map((asset) => (
            <article key={asset.id} className="media-card">
              <div className="media-card__body">
                <div className="media-card__name">{asset.filename}</div>
                <div className="media-card__meta">
                  <span>{asset.mime_type}</span>
                  <span>{asset.size_bytes} bytes</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function DiscussionTab() {
  return (
    <div style={{ maxWidth: "80ch" }}>
      <div className="muted" style={{ padding: "20px 0" }}>Discussion threads will appear here.</div>
      <div style={{ marginTop: 18, border: "1px solid var(--ink)", padding: 14 }}>
        <div className="kicker" style={{ marginBottom: 8 }}>Add comment</div>
        <textarea
          className="edit-textarea"
          style={{ minHeight: 80 }}
          placeholder="Comments are visible to all Researchers and Editors."
        />
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 6 }}>
          <button className="btn btn--primary btn--sm">Post comment</button>
        </div>
      </div>
    </div>
  );
}

function RawTab({ page, revision }: {
  page: import("@/lib/api/types").Page;
  revision: Revision | null | undefined;
}) {
  const frontmatter = `---
slug: ${yamlScalar(page.slug)}
type: ${yamlScalar(page.type)}
status: ${yamlScalar(page.status)}
visibility: ${yamlScalar(page.visibility)}
tags: ${yamlList(page.tags)}
---

# ${revision?.title ?? page.slug}

${revision?.summary ?? ""}

${revision?.content ?? ""}`;

  return (
    <div>
      <div className="kicker" style={{ marginBottom: 10 }}>
        Canonical markdown · {page.slug}.md
      </div>
      <pre className="diff" style={{ padding: 18, fontSize: 12.5, whiteSpace: "pre-wrap", overflowX: "auto" }}>
        {frontmatter}
      </pre>
    </div>
  );
}
