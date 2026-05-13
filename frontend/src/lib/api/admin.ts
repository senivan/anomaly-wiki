import { request } from "./client";
import type { UserRole } from "./types";

export interface AdminUser {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export const adminApi = {
  listUsers: (token: string) =>
    request<AdminUser[]>("/admin/users", { token }),

  setRole: (userId: string, role: UserRole, token: string) =>
    request<AdminUser>(`/admin/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
      token,
    }),
};
