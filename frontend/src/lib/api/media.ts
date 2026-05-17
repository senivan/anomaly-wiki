import { request } from "./client";
import { ApiError } from "./errors";
import type { MediaAsset } from "./types";

export const mediaApi = {
  list: (token: string) =>
    request<MediaAsset[]>("/media", { token }),

  upload: (formData: FormData, token: string) =>
    fetch(
      `${process.env.NEXT_PUBLIC_MEDIA_URL ?? process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8000"}/media`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      },
    ).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail =
          (body as { detail?: string }).detail ??
          (body as { error?: { message?: string } }).error?.message ??
          "Upload failed";
        throw new ApiError(res.status, detail, body);
      }
      return res.json() as Promise<MediaAsset>;
    }),

  getAsset: (assetId: string, token: string) =>
    request<MediaAsset>(`/media/${assetId}`, { token }),

  getByIds: (assetIds: string[], token: string) =>
    request<MediaAsset[]>(`/media/batch?ids=${assetIds.join(",")}`, { token }),

  getDownloadUrl: (assetId: string, token: string) =>
    request<{ url: string }>(`/media/${assetId}/download-url`, { token }),
};
