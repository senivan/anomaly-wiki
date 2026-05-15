"use client";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AuthGuard } from "@/components/ui/AuthGuard";
import { PageTypeChip } from "@/components/ui/PageTypeChip";
import { pagesApi } from "@/lib/api/pages";
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
    queryKey: ["pages", "mine", "Draft"],
    queryFn: () => pagesApi.listMine({ status: "Draft" }, token!),
    enabled: !!token,
  });

  const drafts = data?.pages ?? [];

  return (
    <div>
      <div className="kicker">My desk</div>
      <h1 className="bigtitle" style={{ marginTop: 4, marginBottom: 18 }}>Drafts &amp; pending records</h1>

      {isLoading && (
        <div className="muted">Loading drafts...</div>
      )}

      <div className="results">
        {drafts.map((state) => (
          <div key={state.page.id} className="result-row">
            <div className="result-row__code mono">{state.page.slug}</div>
            <div>
              <div className="row" style={{ gap: 8, marginBottom: 2 }}>
                <PageTypeChip type={state.page.type} />
              </div>
              <h3>{state.current_draft_revision?.title ?? state.page.slug}</h3>
              <p>{state.current_draft_revision?.summary || "No summary provided."}</p>
              <div className="result-row__meta">
                {state.page.tags.slice(0, 3).map((t) => <span key={t}>#{t}</span>)}
              </div>
            </div>
            <div className="result-row__side">
              <button
                className="btn btn--sm"
                onClick={() => router.push(`/edit/${state.page.slug}`)}
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
