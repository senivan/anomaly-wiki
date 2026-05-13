"use client";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AuthGuard } from "@/components/ui/AuthGuard";
import { PageTypeChip } from "@/components/ui/PageTypeChip";
import { StatusPill } from "@/components/ui/StatusPill";
import { searchApi } from "@/lib/api/search";
import { useAuthStore } from "@/lib/store/auth";

export default function DraftsPage() {
  return (
    <AuthGuard minRole="Researcher">
      <DraftsInner />
    </AuthGuard>
  );
}

function DraftsInner() {
  const router = useRouter();
  const { token } = useAuthStore();

  const { data, isLoading } = useQuery({
    queryKey: ["search", "drafts"],
    queryFn: () => searchApi.query({ status: "Draft" }, token ?? undefined),
  });

  const drafts = data?.results ?? [];

  return (
    <div>
      <div className="kicker">My desk</div>
      <h1 className="bigtitle" style={{ marginTop: 4, marginBottom: 18 }}>Drafts &amp; pending records</h1>

      {isLoading && (
        <div className="muted">Loading drafts…</div>
      )}

      <div className="results">
        {drafts.map((p) => (
          <div key={p.page_id} className="result-row">
            <div className="result-row__code mono">{p.slug}</div>
            <div>
              <div className="row" style={{ gap: 8, marginBottom: 2 }}>
                <PageTypeChip type={p.type} />
              </div>
              <h3>{p.title}</h3>
              <p>{p.snippet}</p>
              <div className="result-row__meta">
                {p.tags.slice(0, 3).map((t) => <span key={t}>#{t}</span>)}
              </div>
            </div>
            <div className="result-row__side">
              <button
                className="btn btn--sm"
                onClick={() => router.push(`/edit/${p.slug}`)}
              >
                Continue editing
              </button>
            </div>
          </div>
        ))}
        {!isLoading && drafts.length === 0 && (
          <div className="muted" style={{ padding: "30px 0" }}>
            No drafts on your desk. <span
              style={{ textDecoration: "underline", cursor: "pointer" }}
              onClick={() => router.push("/edit/new")}
            >Create a new record</span>.
          </div>
        )}
      </div>
    </div>
  );
}
