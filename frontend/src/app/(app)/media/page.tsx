"use client";
import { useRef, useState } from "react";
import { useAuthStore } from "@/lib/store/auth";
import { mediaApi } from "@/lib/api/media";
import { Icon } from "@/components/ui/Icon";
import type { MediaAsset } from "@/lib/api/types";

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export default function MediaPage() {
  const { user, token } = useAuthStore();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file: File | undefined) {
    if (!file || !token) return;
    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.set("file", file);
      const asset = await mediaApi.upload(body, token);
      setAssets((current) => [asset, ...current]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-end", marginBottom: 14 }}>
        <div>
          <div className="kicker">media-service · /media</div>
          <h1 className="bigtitle" style={{ marginTop: 4 }}>Media library</h1>
          <div className="muted">
            {assets.length} uploaded asset{assets.length === 1 ? "" : "s"} in this session.
          </div>
        </div>
        {user && user.role !== "Public" && (
          <div className="row">
            <input
              ref={inputRef}
              aria-label="Upload media file"
              type="file"
              style={{ display: "none" }}
              onChange={(event) => upload(event.target.files?.[0])}
            />
            <button
              className="btn btn--primary btn--sm"
              disabled={uploading || !token}
              onClick={() => inputRef.current?.click()}
            >
              <Icon name="upload" size={11} /> {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="callout callout--danger" style={{ marginBottom: 16 }}>
          <div className="callout__title">Error</div>
          {error}
        </div>
      )}

      {assets.length === 0 ? (
        <div className="muted" style={{ padding: "30px 0" }}>
          No media assets have been uploaded in this session.
        </div>
      ) : (
        <div className="media-grid">
          {assets.map((asset) => (
            <article key={asset.id} className="media-card">
              <div className="imgholder" style={{ aspectRatio: "4/3" }}>
                <span>{asset.mime_type}</span>
              </div>
              <div className="media-card__body">
                <div className="media-card__name">{asset.filename}</div>
                <div className="media-card__cap">{asset.id}</div>
                <div className="media-card__meta">
                  <span>{asset.uploaded_by}</span>
                  <span>{formatBytes(asset.size_bytes)} · {asset.created_at.slice(0, 10)}</span>
                </div>
                <div className="row" style={{ gap: 6, marginTop: 10 }}>
                  <span className="tag mono">{asset.content_type ?? asset.mime_type}</span>
                  <span style={{ flex: 1 }} />
                  <span className="mono xsmall muted">{asset.id.slice(0, 8)}</span>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
