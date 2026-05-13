import { request } from "./client";
import type { MediaAsset } from "./types";

export const mediaApi = {
  upload: (formData: FormData, token: string) =>
    fetch(
      `${process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000"}/media`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      },
    ).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { detail?: string }).detail ?? "Upload failed");
      }
      return res.json() as Promise<MediaAsset>;
    }),

  getAsset: (assetId: string, token: string) =>
    request<MediaAsset>(`/media/${assetId}`, { token }),

  getDownloadUrl: (assetId: string, token: string) =>
    request<{ url: string }>(`/media/${assetId}/download-url`, { token }),
};
