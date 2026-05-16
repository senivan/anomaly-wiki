"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore, hasRole } from "@/lib/store/auth";
import { pagesApi } from "@/lib/api/pages";
import { searchApi } from "@/lib/api/search";
import { Icon } from "@/components/ui/Icon";
import { PageTypeChip } from "@/components/ui/PageTypeChip";
import { ImgHolder } from "@/components/ui/ImgHolder";

export default function HomePage() {
  const { user, token } = useAuthStore();
  const router = useRouter();
  const today = new Date().toISOString().slice(0, 10);
  const tok = token ?? undefined;

  const { data: publishedData } = useQuery({
    queryKey: ["search", "recent-published"],
    queryFn: () => searchApi.query({ status: "Published", sort: "updated" }, tok),
  });
  const { data: draftData } = useQuery({
    queryKey: ["pages", "mine", "draft-count", user?.id],
    queryFn: () => pagesApi.listMine({ status: "Draft" }, token!),
    enabled: !!token && !!user && hasRole(user.role, "Researcher"),
  });
  const { data: reviewData } = useQuery({
    queryKey: ["search", "review-count"],
    queryFn: () => searchApi.query({ status: "Review" }, tok),
  });

  const recent = (publishedData?.hits ?? []).slice(0, 4);
  const activity = (publishedData?.hits ?? []).slice(0, 6);
  const publishedTotal = publishedData?.total ?? 0;
  const draftTotal = draftData?.pages.length;
  const reviewTotal = reviewData?.total;

  const name = user?.email.split("@")[0].split(".")[0] ?? "researcher";
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-end", marginBottom: 24 }}>
        <div>
          <div className="kicker">Field terminal · {today}</div>
          <h1 className="bigtitle" style={{ marginTop: 6 }}>{greeting}, {name}.</h1>
          <div className="muted" style={{ maxWidth: "60ch" }}>
            Field Research Terminal — your unified view of the Zone encyclopedia.
            Review pending drafts, search records, and track anomaly activity.
          </div>
        </div>
        {user && hasRole(user.role, "Researcher") && (
          <Link href="/edit/new" className="btn btn--primary btn--sm">
            <Icon name="plus" size={11} /> New record
          </Link>
        )}
      </div>

      <div className="dash-grid dash-grid--3" style={{ marginBottom: 32 }}>
        <div className="kpi">
          <div className="kpi__lab"><span>Published records</span></div>
          <div className="kpi__num">{publishedTotal || "—"}</div>
          <div className="kpi__sub">across 7 record types</div>
        </div>
        <div className="kpi">
          <div className="kpi__lab"><span>Awaiting review</span></div>
          <div className="kpi__num">{reviewTotal ?? "—"}</div>
          <div className="kpi__sub">
            {user && hasRole(user.role, "Editor") ? (
              <Link href="/review" style={{ textDecoration: "none", color: "var(--ink-3)" }}>Open review queue →</Link>
            ) : "Editor sign-off required"}
          </div>
        </div>
        <div className="kpi">
          <div className="kpi__lab"><span>Draft records</span></div>
          <div className="kpi__num">{draftTotal ?? "—"}</div>
          <div className="kpi__sub">
            {user && hasRole(user.role, "Researcher") ? (
              <Link href="/drafts" style={{ textDecoration: "none", color: "var(--ink-3)" }}>View my drafts →</Link>
            ) : "Sign in to see drafts"}
          </div>
        </div>
      </div>

      <div className="dash-grid">
        <section className="card">
          <header className="card__head"><span>Recent activity</span><span className="mono xsmall">recently published</span></header>
          <div className="card__body" style={{ paddingTop: 6 }}>
            {activity.length > 0 ? (
              <div className="feed">
                {activity.map((p) => (
                  <div
                    key={p.page_id}
                    className="feed-item"
                    style={{ cursor: "pointer" }}
                    onClick={() => router.push(`/wiki/${p.slug}`)}
                  >
                    <div className="feed-item__time mono">{p.slug}</div>
                    <div className="feed-item__what">
                      <PageTypeChip type={p.type} /> {p.title}
                    </div>
                    <div className="feed-item__rev">published</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted small" style={{ margin: 0 }}>
                No published records yet. Records will appear here once they are approved.
              </p>
            )}
          </div>
        </section>

        <section className="card">
          <header className="card__head"><span>On your desk</span></header>
          <div className="card__body">
            {user && hasRole(user.role, "Researcher") ? (
              <div>
                <Link
                  href="/drafts"
                  className="btn btn--ghost btn--sm"
                  style={{ width: "100%", justifyContent: "center", marginBottom: 12 }}
                >
                  <Icon name="doc" size={11} /> View my drafts
                </Link>
                <p className="muted small" style={{ margin: 0 }}>
                  Draft records you are actively working on will appear here. Open a draft to continue editing.
                </p>
              </div>
            ) : (
              <p className="muted small" style={{ margin: 0 }}>
                Sign in as a Researcher to see your drafts.
              </p>
            )}
          </div>
        </section>
      </div>

      <hr className="section-divider" />

      <div className="spread" style={{ marginBottom: 14 }}>
        <div>
          <div className="kicker">Recently published</div>
          <h2 className="bigtitle" style={{ fontSize: 24, marginTop: 4 }}>Latest approved records</h2>
        </div>
        <Link href="/search?status=Published" className="btn btn--ghost btn--sm">
          Browse all <Icon name="arrow" size={11} />
        </Link>
      </div>

      {recent.length > 0 ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--gap)" }}>
          {recent.map((p) => (
            <article
              key={p.page_id}
              className="card"
              style={{ cursor: "pointer" }}
              onClick={() => router.push(`/wiki/${p.slug}`)}
            >
              <ImgHolder label={`${p.slug} · field photo`} ratio="16/9" />
              <div className="card__body">
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                  <span className="mono xsmall muted">{p.slug}</span>
                  <PageTypeChip type={p.type} />
                </div>
                <h3 style={{ margin: "0 0 6px", fontFamily: "Newsreader", fontWeight: 500, fontSize: 22 }}>{p.title}</h3>
                <p className="muted" style={{ margin: 0 }}>{p.snippet}</p>
                <div className="row" style={{ marginTop: 12, gap: 6 }}>
                  {(p.tags ?? []).slice(0, 3).map((t) => (
                    <span key={t} className="tag mono">#{t}</span>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="muted" style={{ padding: "30px 0" }}>
          <div className="kicker" style={{ marginBottom: 6 }}>No published records found.</div>
          <p style={{ margin: 0 }}>Start the backend services and seed some records to see them here.</p>
        </div>
      )}
    </div>
  );
}
