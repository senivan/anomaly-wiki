import { request } from "./client";
import type { SearchResponse } from "./types";

export const searchApi = {
  query: (params: { q?: string; type?: string; status?: string; sort?: string }, token?: string) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.type) qs.set("type", params.type);
    if (params.status) qs.set("status", params.status);
    if (params.sort) qs.set("sort", params.sort);
    return request<SearchResponse>(`/search?${qs.toString()}`, { token });
  },

  suggest: (q: string, token?: string) =>
    request<{ suggestions: string[] }>(`/search/suggest?q=${encodeURIComponent(q)}`, { token }),
};
