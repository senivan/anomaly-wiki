import { ApiError } from "./errors";

const GATEWAY =
  typeof window === "undefined"
    ? process.env.GATEWAY_INTERNAL_URL ?? "http://localhost:8000"
    : process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000";

export async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...init } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${GATEWAY}${path}`, { ...init, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const b = body as { detail?: string; error?: { message?: string } };
    const detail = b.detail ?? b.error?.message ?? "Unknown error";
    throw new ApiError(res.status, detail, body);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}
