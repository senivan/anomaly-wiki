"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { pagesApi } from "@/lib/api/pages";
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

  const { data } = useQuery({
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

  useEffect(() => {
    if (data) {
      const rev = data.current_draft_revision ?? data.current_published_revision;
      // eslint-disable-next-line react-hooks/set-state-in-effect
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

  const createMutation = useMutation({
    mutationFn: () => pagesApi.create(
      { slug: newSlug, type, visibility, title, summary, content: md, author_id: user?.id },
      token!,
    ),
    onSuccess: (d) => {
      router.push(`/wiki/${d.page.slug}`);
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

  const handleSave = () => { markDirty(); draftMutation.mutate(); };
  const handleNew  = () => createMutation.mutate();

  const lineCount = md.split("\n").length;
  const charCount = md.length;

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
              onClick={handleNew}
              disabled={createMutation.isPending || !newSlug || !title}
            >
              <Icon name="plus" size={11} /> Create record
            </button>
          ) : (
            <>
              <button
                className="btn btn--sm"
                onClick={handleSave}
                disabled={draftMutation.isPending}
              >
                {draftMutation.isPending ? "Saving…" : "Save draft"}
              </button>
              {hasRole(user?.role ?? "Public", "Researcher") && page?.status === "Draft" && (
                <button
                  className="btn btn--primary btn--sm"
                  onClick={() => submitMutation.mutate()}
                  disabled={submitMutation.isPending}
                >
                  <Icon name="check" size={11} /> Submit for review
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
              onClick={() => { setConflict(false); qc.invalidateQueries({ queryKey: ["page", slug] }); }}
            >
              Reload latest
            </button>
          </div>
        </div>
      )}

      <div className="edit-grid">
        <div className="edit-pane">
          <div className="edit-pane__head">
            <span>Markdown source · {isNew ? newSlug || "untitled" : slug}.md</span>
            <span>{lineCount} ln · {charCount} ch</span>
          </div>
          <textarea
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
          <button className="btn btn--ghost btn--sm">Preview as Public</button>
        </div>
      </div>
    </div>
  );
}
