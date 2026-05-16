"use client";
import { create } from "zustand";
import { jwtDecode } from "jwt-decode";
import type { UserRole } from "@/lib/api/types";

interface JwtPayload {
  sub: string;
  role: UserRole;
  email?: string;
  exp: number;
}

export interface AuthUser {
  id: string;
  email: string;
  role: UserRole;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  login: (token: string) => void;
  logout: () => void;
  hydrate: () => void;
}

export const TOKEN_KEY = "anomaly_wiki_token";

function parseToken(token: string): AuthUser | null {
  try {
    const payload = jwtDecode<JwtPayload>(token);
    if (payload.exp * 1000 < Date.now()) return null;
    return {
      id: payload.sub,
      email: payload.email ?? payload.sub,
      role: payload.role,
    };
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isHydrated: false,

  login: (token) => {
    const user = parseToken(token);
    if (!user) return;
    localStorage.setItem(TOKEN_KEY, token);
    set({ token, user, isAuthenticated: true, isHydrated: true });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    set({ token: null, user: null, isAuthenticated: false, isHydrated: true });
  },

  hydrate: () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      set({ isHydrated: true });
      return;
    }
    const user = parseToken(token);
    if (user) {
      set({ token, user, isAuthenticated: true, isHydrated: true });
    } else {
      localStorage.removeItem(TOKEN_KEY);
      set({ token: null, user: null, isAuthenticated: false, isHydrated: true });
    }
  },
}));

export const ROLE_RANK: Record<UserRole, number> = {
  Public: 0,
  Researcher: 1,
  Editor: 2,
  Admin: 3,
};

export function hasRole(actual: UserRole, required: UserRole): boolean {
  return ROLE_RANK[actual] >= ROLE_RANK[required];
}
