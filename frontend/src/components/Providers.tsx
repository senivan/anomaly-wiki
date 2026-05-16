"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useAuthStore } from "@/lib/store/auth";

function AuthHydrator() {
  const hydrate = useAuthStore((s) => s.hydrate);
  const done = useRef(false);
  useEffect(() => {
    if (!done.current) { hydrate(); done.current = true; }
  }, [hydrate]);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () => new QueryClient({
      defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
    }),
  );
  return (
    <QueryClientProvider client={client}>
      <AuthHydrator />
      {children}
    </QueryClientProvider>
  );
}
