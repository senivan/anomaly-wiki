"use client";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AuthGuard } from "@/components/ui/AuthGuard";
import { Icon } from "@/components/ui/Icon";
import { PageTypeChip } from "@/components/ui/PageTypeChip";
import { searchApi } from "@/lib/api/search";
import { useAuthStore } from "@/lib/store/auth";

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

  const { data, isLoading, error } = useQuery({
    queryKey: ["search", "review"],
    queryFn: () => searchApi.query({ status: "Review" }, token ?? undefined),
  });

  const queue = data?.hits ?? [];

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-end", marginBottom: 14 }}>
        <div>
          <div className="kicker">encyclopedia-service · review queue</div>
          <h1 className="bigtitle" style={{ marginTop: 4 }}>Review queue</h1>
          <div className="muted">
            {isLoading ? "Loading review records..." : `${queue.length} record${queue.length === 1 ? "" : "s"} awaiting Editor sign-off.`}
          </div>
        </div>
      </div>

      {error && (
        <div className="callout callout--danger" style={{ marginBottom: 16 }}>
          <div className="callout__title">Error</div>
          Failed to load review records from search-service.
        </div>
      )}

      <div className="queue-head">
        <span>Slug</span>
        <span>Title</span>
        <span>Type / status</span>
        <span>Visibility</span>
        <span>Action</span>
      </div>

      {queue.map((record) => (
        <div key={record.page_id} className="queue-row">
          <div className="queue-row__code">{record.slug}</div>
          <div>
            <div className="queue-row__title">{record.title}</div>
            <div className="queue-row__meta">{record.summary || record.snippet}</div>
          </div>
          <div className="queue-row__meta">
            <PageTypeChip type={record.type} />
            <div>{record.status}</div>
          </div>
          <div className="queue-row__diff">{record.visibility}</div>
          <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
            <button
              className="btn btn--primary btn--sm"
              onClick={() => router.push(`/wiki/${record.slug}`)}
            >
              <Icon name="check" size={11} /> Open
            </button>
          </div>
        </div>
      ))}

      {!isLoading && queue.length === 0 && (
        <div className="muted" style={{ padding: "30px 0" }}>
          No records are currently awaiting review.
        </div>
      )}
    </div>
  );
}
