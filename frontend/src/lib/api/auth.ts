import { request } from "./client";
import type { AuthToken, CurrentUser } from "./types";

export const authApi = {
  login: (email: string, password: string) =>
    request<AuthToken>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }).toString(),
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }),

  register: (email: string, password: string) =>
    request<CurrentUser>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: (token: string) =>
    request<void>("/auth/logout", { method: "POST", token }),
};
