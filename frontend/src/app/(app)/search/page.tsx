"use client";
import { Suspense } from "react";
import { useState, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { searchApi } from "@/lib/api/search";
import { useAuthStore } from "@/lib/store/auth";
import { Icon } from "@/components/ui/Icon";
import { PageTypeChip } from "@/components/ui/PageTypeChip";
import type { PageStatus, PageType } from "@/lib/api/types";

const PAGE_TYPES: PageType[] = [
  "Anomaly", "Artifact", "Location", "Incident",
  "Expedition", "Researcher Note", "Article",
];

function SearchInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { token } = useAuthStore();

  const [q, setQ]           = useState(params.get("q") ?? "");
  const [type, setType]     = useState<PageType | "">(params.get("type") as PageType ?? "");
  const [status, setStatus] = useState<PageStatus | "">(params.get("status") as PageStatus ?? "");
  const [sort, setSort]     = useState(params.get("sort") ?? "relevance");

  useEffect(() => {
    setQ(params.get("q") ?? "");
    setType((params.get("type") as PageType) ?? "");
    setStatus((params.get("status") as PageStatus) ?? "");
    setSort(params.get("sort") ?? "relevance");
  }, [params]);

  const queryParams = useMemo(
    () => ({ q: q || undefined, type: type || undefined, status: status || undefined, sort }),
    [q, type, status, sort],
  );

  const { data, isFetching } = useQuery({
    queryKey: ["search", queryParams],
    queryFn: () => searchApi.query(queryParams, token ?? undefined),
  });

  const results = data?.results ?? [];
  const total   = data?.total   ?? 0;

  function updateUrl(updates: Record<string, string>) {
    const sp = new URLSearchParams(params.toString());
    Object.entries(updates).forEach(([k, v]) => {
      if (v) sp.set(k, v); else sp.delete(k);
    });
    router.replace(`/search?${sp.toString()}`);
  }

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-end", marginBottom: 18 }}>
        <div>
          <div className="kicker">search-service · /v1/query</div>
          <h1 className="bigtitle" style={{ marginTop: 6 }}>Search the archive</h1>
        </div>
        <div className="mono xsmall muted">
          {isFetching ? "querying…" : `${total} record${total === 1 ? "" : "s"} matched`}
        </div>
      </div>

      <div className="searchbox" style={{ marginBottom: 6, height: 48 }}>
        <Icon name="search" size={16} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") updateUrl({ q }); }}
          placeholder="type:Anomaly tag:gravimetric severity:Lethal …"
        />
        <span className="mono xsmall muted">⏎ to query</span>
      </div>

      <div className="filterbar">
        <span className="filterbar__lab">Type</span>
        <span
          className={`chip ${!type ? "is-active" : ""}`}
          onClick={() => { setType(""); updateUrl({ type: "" }); }}
        >All</span>
        {PAGE_TYPES.map((t) => (
          <span
            key={t}
            className={`chip ${type === t ? "is-active" : ""}`}
            onClick={() => { const next = type === t ? "" : t; setType(next); updateUrl({ type: next }); }}
          >{t}</span>
        ))}
      </div>

      <div className="filterbar">
        <span className="filterbar__lab">Status</span>
        {(["", "Published", "Review", "Draft"] as const).map((s) => (
          <span
            key={s || "all"}
            className={`chip ${status === s ? "is-active" : ""}`}
            onClick={() => { setStatus(s as PageStatus | ""); updateUrl({ status: s }); }}
          >{s || "All"}</span>
        ))}
        <span style={{ flex: 1 }} />
        <span className="filterbar__lab">Sort</span>
        <span className={`chip ${sort === "relevance" ? "is-active" : ""}`} onClick={() => { setSort("relevance"); updateUrl({ sort: "relevance" }); }}>Relevance</span>
        <span className={`chip ${sort === "updated" ? "is-active" : ""}`} onClick={() => { setSort("updated"); updateUrl({ sort: "updated" }); }}>Last updated</span>
      </div>

      <div className="results">
        {results.map((p) => (
          <div key={p.page_id} className="result-row" onClick={() => router.push(`/wiki/${p.slug}`)}>
            <div className="result-row__code mono">{p.slug}</div>
            <div>
              <div className="row" style={{ gap: 8, marginBottom: 2 }}>
                <PageTypeChip type={p.type} />
              </div>
              <h3>{p.title}</h3>
              <p>{p.snippet}</p>
              <div className="result-row__meta">
                {p.tags.slice(0, 4).map((t) => <span key={t}>#{t}</span>)}
              </div>
            </div>
            <div className="result-row__side">
              <span className="mono xsmall">{p.slug}</span>
            </div>
          </div>
        ))}
        {!isFetching && results.length === 0 && (
          <div className="muted" style={{ padding: "30px 0" }}>
            No records match. Try removing a filter.
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="muted">Loading search…</div>}>
      <SearchInner />
    </Suspense>
  );
}
