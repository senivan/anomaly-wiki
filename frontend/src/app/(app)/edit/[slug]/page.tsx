"use client";
import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { pagesApi } from "@/lib/api/pages";
import { mediaApi } from "@/lib/api/media";
import { useAuthStore, hasRole } from "@/lib/store/auth";
import { useEditorStore } from "@/lib/store/editor";
import { AuthGuard } from "@/components/ui/AuthGuard";
import { Icon } from "@/components/ui/Icon";
import { ApiError } from "@/lib/api/errors";
import type { PageType, Visibility } from "@/lib/api/types";

const WORKFLOW_STEPS = [
  { name: "Draft",     blurb: "Author works the record." },
  { name: "Review",    blurb: "Editor inspects the diff." },
  { name: "Published", blurb: "Public record of truth." },
  { name: "Archived",  blurb: "Superseded or redacted." },
];

const PAGE_TYPES: PageType[] = ["Anomaly", "Artifact", "Location", "Incident", "Expedition", "Researcher Note", "Article"];

export default function EditPage() {
  const { slug } = useParams<{ slug: string }>();
  const isNew = slug === "new";

  return (
    <AuthGuard minRole="Researcher">
      <EditPageInner slug={slug} isNew={isNew} />
    </AuthGuard>
  );
}

function EditPageInner({ slug, isNew }: { slug: string; isNew: boolean }) {
  const router = useRouter();
  const { user, token } = useAuthStore();
  const { setBaseline, markDirty, reset } = useEditorStore();
  const qc = useQueryClient();

  const { data, isFetching, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["page", slug],
    queryFn: () => pagesApi.getBySlug(slug, token ?? undefined),
    enabled: !isNew,
  });

  const page = data?.page;
  const revision = data?.current_draft_revision ?? data?.current_published_revision;

  const [title, setTitle]     = useState("");
  const [summary, setSummary] = useState("");
  const [md, setMd]           = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [type, setType]       = useState<PageType>("Anomaly");
  const [visibility, setVis]  = useState<Visibility>("Internal");
  const [conflict, setConflict] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [imgUploading, setImgUploading] = useState(false);
  const [imgError, setImgError] = useState<string | null>(null);
  const [pendingAssetIds, setPendingAssetIds] = useState<string[]>([]);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const imgInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (data) {
      const rev = data.current_draft_revision ?? data.current_published_revision;
      setTitle(rev?.title ?? "");
      setSummary(rev?.summary ?? "");
      setMd(rev?.content ?? "");
      setBaseline(data.page.id, data.page.version);
    }
  }, [data, setBaseline]);

  useEffect(() => () => { reset(); }, [reset]);

  const stepIndex =
    page?.status === "Draft"     ? 0 :
    page?.status === "Review"    ? 1 :
    page?.status === "Published" ? 2 :
    page?.status === "Archived"  ? 3 : 0;

  async function insertImage(file: File) {
    if (!token) return;
    setImgUploading(true);
    setImgError(null);
    try {
      const formData = new FormData();
      formData.set("file", file);
      const asset = await mediaApi.upload(formData, token);

      if (page && !isNew) {
        const existing = page.media_asset_ids ?? [];
        if (!existing.includes(asset.id)) {
          const updated = await pagesApi.updateMetadata(
            page.id,
            { expected_page_version: page.version, media_asset_ids: [...existing, asset.id] },
            token,
          );
          qc.setQueryData(["page", slug], updated);
          setBaseline(updated.page.id, updated.page.version);
        }
      } else {
        setPendingAssetIds((prev) => [...prev, asset.id]);
      }

      const { url } = await mediaApi.getDownloadUrl(asset.id, token);
      const snippet = `![${asset.filename}](${url})`;

      const ta = textareaRef.current;
      if (ta) {
        const s = ta.selectionStart ?? md.length;
        const e = ta.selectionEnd ?? md.length;
        const next = md.slice(0, s) + snippet + md.slice(e);
        setMd(next);
        requestAnimationFrame(() => {
          ta.selectionStart = ta.selectionEnd = s + snippet.length;
          ta.focus();
        });
      } else {
        setMd((prev) => prev + (prev ? "\n\n" : "") + snippet);
      }
      markDirty();
    } catch (err) {
      setImgError(err instanceof Error ? err.message : "Image upload failed.");
    } finally {
      setImgUploading(false);
      if (imgInputRef.current) imgInputRef.current.value = "";
    }
  }

  const createMutation = useMutation({
    mutationFn: () => pagesApi.create(
      { slug: newSlug, type, visibility, title, summary, content: md, author_id: user?.id },
      token!,
    ),
    onSuccess: async (d) => {
      if (pendingAssetIds.length > 0) {
        try {
          await pagesApi.updateMetadata(
            d.page.id,
            { expected_page_version: d.page.version, media_asset_ids: pendingAssetIds },
            token!,
          );
        } catch {
          // non-fatal: images still visible via presigned URL while fresh
        }
      }
      reset();
      router.push(`/wiki/${d.page.slug}`);
    },
    onError: (e) => {
      setCreateError(e instanceof ApiError ? e.message : "Failed to create record.");
    },
  });

  const draftMutation = useMutation({
    mutationFn: () => pagesApi.createDraft(
      page!.id,
      {
        parent_revision_id: page!.current_draft_revision_id,
        title,
        summary,
        content: md,
        expected_page_version: page!.version,
        author_id: user?.id,
      },
      token!,
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["page", slug] });
      setSaveMsg("Saved.");
      setTimeout(() => setSaveMsg(null), 3000);
      reset();
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) setConflict(true);
      else {
        setSaveError(e instanceof ApiError ? e.message : "Save failed.");
        setTimeout(() => setSaveError(null), 6000);
      }
    },
  });

  const submitMutation = useMutation({
    mutationFn: () => pagesApi.transitionStatus(
      page!.id,
      { status: "Review", expected_page_version: page!.version },
      token!,
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["page", slug] });
      router.push(`/wiki/${slug}`);
    },
  });

  const handleSave = () => { draftMutation.mutate(); };
  const handleNew  = () => createMutation.mutate();

  const handleConflictReload = () => {
    const ok = window.confirm(
      "Reloading will discard your unsaved edits. Continue?",
    );
    if (!ok) return;
    setConflict(false);
    qc.invalidateQueries({ queryKey: ["page", slug] });
  };

  const lineCount = md.split("\n").length;
  const charCount = md.length;

  if (!isNew && isLoading) {
    return (
      <div>
        <div className="page-header">
          <div>
            <div className="kicker">Loading record...</div>
            <div style={{ height: 48, background: "var(--paper-2)", margin: "12px 0", width: "60%" }} />
            <div style={{ height: 16, background: "var(--paper-2)", marginTop: 10, width: "40%" }} />
          </div>
        </div>
        <div className="edit-grid">
          <div className="edit-pane">
            <div className="edit-pane__head"><span>Markdown source</span></div>
            <div style={{ height: 240, background: "var(--paper-2)" }} />
          </div>
          <div className="edit-pane">
            <div className="edit-pane__head"><span>Live preview</span></div>
            <div style={{ height: 240, background: "var(--paper-2)" }} />
          </div>
        </div>
      </div>
    );
  }

  if (!isNew && (isError || !data)) {
    return (
      <div className="callout callout--danger" style={{ maxWidth: "none" }}>
        <div className="callout__title"><Icon name="alert" size={11} /> Failed to load record</div>
        <div style={{ marginBottom: 12 }}>
          {error instanceof Error ? error.message : "The page could not be loaded."}
        </div>
        <button
          className="btn btn--ghost btn--sm"
          onClick={() => void refetch()}
          disabled={isFetching}
        >
          {isFetching ? "Retrying..." : "Retry"}
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-start", marginBottom: 14 }}>
        <div>
          <div className="kicker">
            {isNew
              ? "encyclopedia-service · /v1/pages — new"
              : `encyclopedia-service · /v1/pages/${slug}`}
          </div>
          <h1 className="bigtitle" style={{ marginTop: 4 }}>
            {isNew ? "Create new record" : `Editing — ${title || slug}`}
          </h1>
          <div className="muted xsmall mono">
            {isNew
              ? `new record · draft · ${user?.email ?? "unknown"}`
              : `${slug} · draft · ${user?.email ?? "unknown"}`}
          </div>
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => router.back()}
          >
            <Icon name="x" size={11} /> Cancel
          </button>
          {isNew ? (
            <button
              className="btn btn--primary btn--sm"
              onClick={() => { setCreateError(null); handleNew(); }}
              disabled={createMutation.isPending || !newSlug || !title || !md}
            >
              <Icon name="plus" size={11} />
              {createMutation.isPending ? "Creating…" : "Create record"}
            </button>
          ) : (
            <>
              <button
                className="btn btn--sm"
                onClick={handleSave}
                disabled={draftMutation.isPending || !md}
              >
                {draftMutation.isPending ? "Saving…" : "Save draft"}
              </button>
              {hasRole(user?.role ?? "Public", "Researcher") && page?.status === "Draft" && (
                <button
                  className="btn btn--primary btn--sm"
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending || (data !== undefined && isFetching) || draftMutation.isPending}
                >
                  <Icon name="check" size={11} /> {(data !== undefined && isFetching) ? "Syncing…" : "Submit for review"}
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {!isNew && (
        <div className="workflow" style={{ marginBottom: 18 }}>
          {WORKFLOW_STEPS.map((s, i) => (
            <div
              key={s.name}
              className={`workflow__step ${i < stepIndex ? "is-done" : ""} ${i === stepIndex ? "is-current" : ""}`}
            >
              <span className="num">0{i + 1}</span>
              <span>
                <b>{s.name}</b>
                <br />
                <span style={{ textTransform: "none", letterSpacing: 0, fontSize: 10, opacity: 0.75 }}>
                  {s.blurb}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}

      {isNew && (
        <div style={{ border: "1px solid var(--ink)", padding: 18, marginBottom: 18 }}>
          <div className="kicker" style={{ marginBottom: 12 }}>New record metadata</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            <div className="form-field">
              <label htmlFor="page-slug">Slug (URL identifier)</label>
              <input
                id="page-slug"
                value={newSlug}
                onChange={(e) => setNewSlug(e.target.value.toLowerCase().replace(/\s+/g, "-"))}
                placeholder="gravity-funnel"
              />
            </div>
            <div className="form-field">
              <label htmlFor="page-type">Type</label>
              <select
                id="page-type"
                value={type}
                onChange={(e) => setType(e.target.value as PageType)}
                style={{ border: "1px solid var(--rule)", background: "var(--paper-2)", padding: "9px 12px", fontFamily: "JetBrains Mono", fontSize: 13, color: "var(--ink)" }}
              >
                {PAGE_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="page-visibility">Visibility</label>
              <select
                id="page-visibility"
                value={visibility}
                onChange={(e) => setVis(e.target.value as Visibility)}
                style={{ border: "1px solid var(--rule)", background: "var(--paper-2)", padding: "9px 12px", fontFamily: "JetBrains Mono", fontSize: 13, color: "var(--ink)" }}
              >
                <option>Internal</option>
                <option>Public</option>
              </select>
            </div>
          </div>
        </div>
      )}

      <div style={{ marginBottom: 14, display: "flex", gap: 8, fontFamily: "JetBrains Mono", fontSize: 12, flexWrap: "wrap" }}>
        <div className="form-field" style={{ marginBottom: 0, flex: 1, minWidth: 200 }}>
          <label htmlFor="page-title">Title</label>
          <input id="page-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Record title" />
        </div>
        <div className="form-field" style={{ marginBottom: 0, flex: 2, minWidth: 300 }}>
          <label htmlFor="page-summary">Summary</label>
          <input id="page-summary" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="One-sentence summary" />
        </div>
      </div>

      {!isNew && (
        <div className="row" style={{ gap: 8, marginBottom: 14, fontFamily: "JetBrains Mono", fontSize: 12 }}>
          <span className="tag">Type · {page?.type ?? "—"}</span>
          <span className="tag">Slug · /{slug}</span>
          <span className="tag">Visibility · {page?.visibility ?? "—"}</span>
          <span style={{ flex: 1 }} />
          <span className="muted xsmall">Optimistic lock: held by you</span>
        </div>
      )}

      {conflict && (
        <div className="callout callout--danger" style={{ marginBottom: 14 }}>
          <div className="callout__title"><Icon name="alert" size={11} /> Version conflict</div>
          <div>
            Another user modified this record. Please{" "}
            <button
              className="btn btn--ghost btn--sm"
              onClick={handleConflictReload}
            >
              Reload latest
            </button>
          </div>
        </div>
      )}

      {createError && (
        <div className="callout callout--danger" style={{ marginBottom: 14 }}>
          <div className="callout__title"><Icon name="alert" size={11} /> Failed to create record</div>
          <div>{createError}</div>
        </div>
      )}

      {imgError && (
        <div className="callout callout--danger" style={{ marginBottom: 14 }}>
          <div className="callout__title"><Icon name="alert" size={11} /> Image upload failed</div>
          <div>{imgError}</div>
        </div>
      )}

      <div className="edit-grid">
        <div className="edit-pane">
          <div className="edit-pane__head">
            <span>Markdown source · {isNew ? newSlug || "untitled" : slug}.md</span>
            <div className="row" style={{ gap: 6 }}>
              <span>{lineCount} ln · {charCount} ch</span>
              <input
                ref={imgInputRef}
                type="file"
                accept="image/*"
                style={{ display: "none" }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) insertImage(f); }}
              />
              <button
                className="btn btn--ghost btn--sm"
                style={{ padding: "0 6px", fontSize: 11 }}
                disabled={imgUploading || !token}
                onClick={() => imgInputRef.current?.click()}
                title="Upload and insert image"
              >
                <Icon name="upload" size={10} /> {imgUploading ? "Uploading…" : "Image"}
              </button>
            </div>
          </div>
          <textarea
            ref={textareaRef}
            className="edit-textarea"
            value={md}
            onChange={(e) => { setMd(e.target.value); markDirty(); }}
            spellCheck={false}
            placeholder="## Field characteristics&#10;&#10;Begin writing the record content here…"
          />
        </div>
        <div className="edit-pane">
          <div className="edit-pane__head">
            <span>Live preview</span>
            <span>encyclopedia-svc render</span>
          </div>
          <div className="edit-preview prose">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ children }) => <table className="field-table">{children}</table>,
                blockquote: ({ children }) => (
                  <div className="callout callout--info">
                    <div className="callout__title"><Icon name="shield" size={11} />Note</div>
                    <div>{children}</div>
                  </div>
                ),
              }}
            >
              {md || "*Start typing to see a preview…*"}
            </ReactMarkdown>
          </div>
        </div>
      </div>

      <div className="spread" style={{ marginTop: 14 }}>
        <div className="muted xsmall mono">
          {saveMsg ?? `revision r${revision ? "n+1" : "1"} (draft)`}
        </div>
        <div className="row" style={{ gap: 6 }}>
          <button
            className="btn btn--ghost btn--sm"
            disabled={isNew}
            onClick={() => window.open(`/wiki/${slug}`, "_blank")}
          >
            Preview as Public
          </button>
        </div>
      </div>

      {saveError && (
        <div style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 1000,
          maxWidth: 360, padding: "12px 16px",
          background: "var(--color-danger, #c0392b)", color: "#fff",
          borderRadius: 6, boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
          display: "flex", gap: 12, alignItems: "flex-start",
        }}>
          <Icon name="alert" size={14} />
          <span style={{ flex: 1, fontSize: 13 }}>{saveError}</span>
          <button
            onClick={() => setSaveError(null)}
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, lineHeight: 1 }}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
