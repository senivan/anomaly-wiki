"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { useAuthStore } from "@/lib/store/auth";

function useTheme() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("anomaly_wiki_theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = stored ? stored === "dark" : prefersDark;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDark(isDark);
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "");
  }, []);

  function toggle() {
    setDark((prev) => {
      const next = !prev;
      document.documentElement.setAttribute("data-theme", next ? "dark" : "");
      localStorage.setItem("anomaly_wiki_theme", next ? "dark" : "light");
      return next;
    });
  }

  return { dark, toggle };
}

export function Topbar() {
  const [q, setQ] = useState("");
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { dark, toggle } = useTheme();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        router.push("/search");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  const initials = user
    ? user.email.split(/[@.]/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join("")
    : "??";

  return (
    <header className="topbar">
      <Link href="/" className="topbar__brand" style={{ textDecoration: "none" }}>
        <div className="brand__mark" />
        <div className="brand__title">
          <b>Anomaly Wiki</b>
          <small>Field Research Terminal · v2.4</small>
        </div>
      </Link>

      <div className="topbar__search">
        <div className="searchbox">
          <Icon name="search" size={14} />
          <input
            placeholder="Search anomalies, artifacts, incidents… (try: type:Anomaly tag:gravimetric)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") router.push(`/search?q=${encodeURIComponent(q)}`);
            }}
          />
        </div>
        <button
          className="btn btn--ghost btn--sm"
          onClick={toggle}
          title={dark ? "Switch to light mode" : "Switch to dark mode"}
          style={{ padding: "0 8px" }}
        >
          <Icon name={dark ? "sun" : "moon"} size={14} />
        </button>
        {isAuthenticated && user?.role !== "Public" && (
          <Link href="/edit/new" className="btn btn--primary btn--sm">
            <Icon name="plus" size={12} /> New page
          </Link>
        )}
      </div>

      <div className="topbar__user">
        {isAuthenticated && user ? (
          <div className="userchip">
            <div className="userchip__avatar mono">{initials}</div>
            <div className="userchip__meta">
              <b>{user.email.split("@")[0]}</b>
              <span>{user.role} · L2</span>
            </div>
          </div>
        ) : (
          <Link href="/login" className="btn btn--sm">Sign in</Link>
        )}
        {isAuthenticated && (
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => { logout(); router.push("/"); }}
          >
            <Icon name="x" size={11} />
          </button>
        )}
      </div>
    </header>
  );
}
