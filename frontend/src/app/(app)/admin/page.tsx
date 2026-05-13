"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/lib/store/auth";
import { adminApi, type AdminUser } from "@/lib/api/admin";
import { AuthGuard } from "@/components/ui/AuthGuard";
import type { UserRole } from "@/lib/api/types";

const ROLES: UserRole[] = ["Public", "Researcher", "Editor", "Admin"];

function UserRow({ user, token }: { user: AdminUser; token: string }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<UserRole>(user.role);

  const { mutate, isPending } = useMutation({
    mutationFn: (role: UserRole) => adminApi.setRole(user.id, role, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  const dirty = selected !== user.role;

  return (
    <tr>
      <td className="mono" style={{ padding: "10px 12px", fontSize: 13 }}>{user.email}</td>
      <td style={{ padding: "10px 12px" }}>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value as UserRole)}
          style={{
            fontFamily: "inherit",
            fontSize: 13,
            background: "var(--paper-2)",
            color: "var(--ink)",
            border: "1px solid var(--rule)",
            padding: "3px 8px",
          }}
        >
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </td>
      <td style={{ padding: "10px 12px" }}>
        <button
          className="btn btn--primary btn--sm"
          disabled={!dirty || isPending}
          onClick={() => mutate(selected)}
        >
          {isPending ? "Saving…" : "Apply"}
        </button>
      </td>
      <td style={{ padding: "10px 12px" }}>
        <span
          className="mono xsmall"
          style={{ color: user.is_active ? "var(--safe)" : "var(--danger)" }}
        >
          ● {user.is_active ? "active" : "inactive"}
        </span>
      </td>
    </tr>
  );
}

export default function AdminPage() {
  const { token } = useAuthStore();

  const { data: users, isFetching, error } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => adminApi.listUsers(token!),
    enabled: !!token,
  });

  return (
    <AuthGuard minRole="Admin">
      <div>
        <div className="kicker">admin · /admin/users</div>
        <h1 className="bigtitle" style={{ marginTop: 6, marginBottom: 24 }}>User management</h1>

        {error && (
          <div className="callout callout--danger" style={{ marginBottom: 16 }}>
            <div className="callout__title">Error</div>
            Failed to load users. Make sure you are signed in as Admin.
          </div>
        )}

        <div className="card">
          <header className="card__head">
            <span>Registered researchers</span>
            <span className="mono xsmall muted">{isFetching ? "loading…" : `${users?.length ?? 0} accounts`}</span>
          </header>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--rule)" }}>
                  <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Email</th>
                  <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Role</th>
                  <th style={{ padding: "8px 12px" }} />
                  <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {(users ?? []).map((u) => (
                  <UserRow key={u.id} user={u} token={token!} />
                ))}
                {!isFetching && !users?.length && (
                  <tr>
                    <td colSpan={4} className="muted" style={{ padding: "24px 12px" }}>
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="callout callout--warn" style={{ marginTop: 20 }}>
          <div className="callout__title">Note</div>
          Role changes take effect on the user's next login — their current session token keeps the old role until they sign out and back in.
        </div>
      </div>
    </AuthGuard>
  );
}
