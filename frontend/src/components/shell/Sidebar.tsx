"use client";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore, hasRole } from "@/lib/store/auth";
import { useQuery } from "@tanstack/react-query";

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuthStore();

  interface ServiceStatus { status: "ok" | "error"; status_code?: number; }
  interface ReadyResponse { status: string; services: Record<string, ServiceStatus>; }

  const { data: ready } = useQuery({
    queryKey: ["service-health"],
    queryFn: async (): Promise<ReadyResponse | null> => {
      const res = await fetch(`${process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000"}/ready`).catch(() => null);
      if (!res) return null;
      return res.json();
    },
    refetchInterval: 30_000,
  });

  const nav = (path: string) => router.push(path);
  const isActive = (path: string) => pathname === path || pathname.startsWith(path + "/");

  return (
    <aside className="sidebar">
      <ul className="nav-list">
        <li className={`nav-item ${pathname === "/" ? "is-active" : ""}`} onClick={() => nav("/")}>
          <span>Dashboard</span>
        </li>
        <li className={`nav-item ${isActive("/search") ? "is-active" : ""}`} onClick={() => nav("/search")}>
          <span>Search</span>
        </li>
        <li className={`nav-item ${isActive("/media") ? "is-active" : ""}`} onClick={() => nav("/media")}>
          <span>Media library</span>
        </li>
      </ul>

      {user && hasRole(user.role, "Researcher") && (
        <>
          <div className="side-h"><span>Researcher</span></div>
          <ul className="nav-list">
            {hasRole(user.role, "Editor") && (
              <li className={`nav-item ${isActive("/review") ? "is-active" : ""}`} onClick={() => nav("/review")}>
                <span>Review queue</span>
              </li>
            )}
            <li className={`nav-item ${isActive("/drafts") ? "is-active" : ""}`} onClick={() => nav("/drafts")}>
              <span>My drafts</span>
            </li>
            {hasRole(user.role, "Admin") && (
              <li className={`nav-item ${isActive("/admin") ? "is-active" : ""}`} onClick={() => nav("/admin")}>
                <span>User management</span>
              </li>
            )}
          </ul>
        </>
      )}

      <div className="side-h"><span>System</span></div>
      <ul className="nav-list">
        {[
          { key: "gateway",                  label: "api-gateway" },
          { key: "researcher_auth_service",  label: "auth-svc" },
          { key: "encyclopedia_service",     label: "encyclopedia-svc" },
          { key: "media_service",            label: "media-svc" },
          { key: "search_service",           label: "search-svc" },
        ].map(({ key, label }) => {
          const svc = key === "gateway" ? null : ready?.services?.[key];
          const status = key === "gateway"
            ? (ready === undefined ? undefined : ready !== null ? "ok" : "err")
            : svc?.status;
          const color = status === "ok" ? "var(--safe)" : status === "error" || status === "err" ? "var(--danger)" : "var(--ink-3)";
          return (
            <li key={key} className="nav-item">
              <span>{label}</span>
              <span className="nav-meta" style={{ color }}>● {status ?? "…"}</span>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
