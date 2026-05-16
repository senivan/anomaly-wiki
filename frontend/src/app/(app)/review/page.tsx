"use client";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AuthGuard } from "@/components/ui/AuthGuard";
import { Icon } from "@/components/ui/Icon";
import { PageTypeChip } from "@/components/ui/PageTypeChip";
import { pagesApi } from "@/lib/api/pages";
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
  const authToken = token!;

  const { data, isLoading, error } = useQuery({
    queryKey: ["search", "review"],
    queryFn: () => searchApi.query({ status: "Review" }, token ?? undefined),
  });

  const qc = useQueryClient();

  const publishMutation = useMutation({
    mutationFn: async (pageId: string) => {
      const state = await pagesApi.getById(pageId, authToken);
      const draftRevisionId = state.page.current_draft_revision_id;
      if (!draftRevisionId) throw new Error("No draft revision available to publish.");
      return pagesApi.publish(
        pageId,
        { revision_id: draftRevisionId, expected_page_version: state.page.version },
        authToken,
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["search", "review"] }),
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

      {publishMutation.error && (
        <div className="callout callout--danger" style={{ marginBottom: 16 }}>
          <div className="callout__title">Publish failed</div>
          {publishMutation.error instanceof Error ? publishMutation.error.message : "An unexpected error occurred."}
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
              className="btn btn--ghost btn--sm"
              onClick={() => router.push(`/wiki/${record.slug}`)}
            >
              <Icon name="arrow" size={11} /> Open
            </button>
            <button
              className="btn btn--primary btn--sm"
              disabled={publishMutation.isPending}
              onClick={() => publishMutation.mutate(record.page_id)}
            >
              <Icon name="check" size={11} /> Publish
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
