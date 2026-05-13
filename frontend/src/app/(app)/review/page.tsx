"use client";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AuthGuard } from "@/components/ui/AuthGuard";
import { Icon } from "@/components/ui/Icon";
import { Callout } from "@/components/ui/Callout";
import { pagesApi } from "@/lib/api/pages";
import { useAuthStore } from "@/lib/store/auth";

const MOCK_QUEUE = [
  { id: "rv1", pageId: "—", slug: "incident-2026-04-22", code: "INC-2026-014", title: "Funnel cluster, Northern Marshes — 22 Apr 2026", type: "Incident", severity: "Severe", author: "d.bykov", submitted: "2026-05-05 08:51", diff: "+184 / −12", urgency: "high" as const },
  { id: "rv2", pageId: "—", slug: "compass-fault",        code: "AR-024",       title: "Compass-fault",                                   type: "Artifact",  severity: "Routine", author: "a.petrenko", submitted: "2026-05-04 22:03", diff: "+96 / −0",   urgency: "low"  as const },
  { id: "rv3", pageId: "—", slug: "expedition-northern",  code: "EXP-2026-Q2",  title: "Q2 Northern Marshes survey",                      type: "Expedition", severity: "Routine", author: "v.komarov",  submitted: "2026-05-04 17:29", diff: "+220 / −0",  urgency: "med"  as const },
];

export default function ReviewPage() {
  return (
    <AuthGuard minRole="Editor">
      <ReviewInner />
    </AuthGuard>
  );
}

function ReviewInner() {
  const router = useRouter();
  const { token } = useAuthStore();
  const qc = useQueryClient();

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-end", marginBottom: 14 }}>
        <div>
          <div className="kicker">encyclopedia-service · /v1/reviews</div>
          <h1 className="bigtitle" style={{ marginTop: 4 }}>Review queue</h1>
          <div className="muted">{MOCK_QUEUE.length} drafts awaiting Editor sign-off. Editorial standard: 24h response on Severity ≥ Severe.</div>
        </div>
        <div className="row">
          <button className="btn btn--ghost btn--sm">My queue</button>
          <button className="btn btn--sm">All editors</button>
        </div>
      </div>

      <div className="queue-head">
        <span>Code</span>
        <span>Title</span>
        <span>Author / submitted</span>
        <span>Diff</span>
        <span>Action</span>
      </div>

      {MOCK_QUEUE.map((r) => (
        <div key={r.id} className="queue-row">
          <div className="queue-row__code">
            <span
              className={`urgency urgency--${r.urgency}`}
              aria-label={`Urgency: ${r.urgency}`}
            />
            {r.code}
          </div>
          <div>
            <div className="queue-row__title">{r.title}</div>
            <div className="queue-row__meta">{r.type} · {r.severity}</div>
          </div>
          <div className="queue-row__meta">
            <div>{r.author}</div>
            <div>{r.submitted}</div>
          </div>
          <div className="queue-row__diff">{r.diff}</div>
          <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => router.push(`/wiki/${r.slug}`)}
            >
              Open
            </button>
            <button className="btn btn--sm">
              <Icon name="check" size={11} /> Approve
            </button>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 32 }}>
        <div className="kicker" style={{ marginBottom: 8 }}>Service contract</div>
        <Callout tone="info" title="api-gateway → encyclopedia-service">
          <div className="mono xsmall" style={{ lineHeight: 1.6 }}>
            POST /pages/&#123;id&#125;/status → {"{"} new_status: "Published" {"}"}<br />
            ↳ emits PageStatusChangedEvent (Draft → Review → <b>Published</b>)<br />
            ↳ search-indexer picks up within ≤ 5s; lag indicator visible in sidebar
          </div>
        </Callout>
      </div>
    </div>
  );
}
