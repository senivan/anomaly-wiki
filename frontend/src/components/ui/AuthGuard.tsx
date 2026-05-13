"use client";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAuthStore, hasRole } from "@/lib/store/auth";
import type { UserRole } from "@/lib/api/types";

interface AuthGuardProps {
  minRole?: UserRole;
  children: ReactNode;
}

export function AuthGuard({ minRole = "Researcher", children }: AuthGuardProps) {
  const { user, isAuthenticated } = useAuthStore();
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace(`/login?redirect=${encodeURIComponent(path)}`);
    } else if (user && !hasRole(user.role, minRole)) {
      router.replace("/");
    }
  }, [isAuthenticated, user, minRole, router, path]);

  if (!isAuthenticated || !user) return null;
  if (!hasRole(user.role, minRole)) return null;
  return <>{children}</>;
}
