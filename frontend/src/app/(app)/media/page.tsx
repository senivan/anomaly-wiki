"use client";
import { useState } from "react";
import { useAuthStore } from "@/lib/store/auth";
import { Icon } from "@/components/ui/Icon";
import { ImgHolder } from "@/components/ui/ImgHolder";

type MediaFilter = "all" | "image" | "audio" | "pdf";

const MOCK_MEDIA = [
  { id: "m-001", filename: "AN-047_funnel_perimeter_01.jpg", type: "image", size: "3.4 MB", uploadedBy: "v.komarov",  at: "2026-04-22", page: "gravity-funnel",   caption: "Northern Marshes, eastern column" },
  { id: "m-002", filename: "AN-047_bolt_trace_seq.gif",      type: "image", size: "1.1 MB", uploadedBy: "v.komarov",  at: "2026-04-22", page: "gravity-funnel",   caption: "Marker-bolt deflection test" },
  { id: "m-003", filename: "AR-018_stone_blood_specimen.jpg",type: "image", size: "2.8 MB", uploadedBy: "i.shevhcuk", at: "2024-07-02", page: "stone-blood",      caption: "Specimen 03, dorsal view" },
  { id: "m-004", filename: "AN-061_field_audio_2026-03-14.wav", type: "audio", size: "12 MB", uploadedBy: "a.petrenko", at: "2026-03-14", page: "spectral-haze", caption: "Field recording, 06:21" },
  { id: "m-005", filename: "INC-2026-014_recovery_report.pdf",  type: "pdf",   size: "0.7 MB", uploadedBy: "d.bykov",   at: "2026-04-23", page: "incident-2026", caption: "Field recovery report" },
  { id: "m-006", filename: "LOC-04_red_forest_panorama.jpg",    type: "image", size: "5.2 MB", uploadedBy: "i.shevhcuk", at: "2025-10-11", page: "red-forest",   caption: "Eastern edge, dawn" },
];

export default function MediaPage() {
  const { user } = useAuthStore();
  const [filter, setFilter] = useState<MediaFilter>("all");

  const items = MOCK_MEDIA.filter((m) => filter === "all" || m.type === filter);
  const totalSize = "25.2 MB";

  return (
    <div>
      <div className="spread" style={{ alignItems: "flex-end", marginBottom: 14 }}>
        <div>
          <div className="kicker">media-service · /v1/assets</div>
          <h1 className="bigtitle" style={{ marginTop: 4 }}>Media library</h1>
          <div className="muted">
            {MOCK_MEDIA.length} assets · {totalSize} · S3 bucket{" "}
            <span className="mono">aw-media-prod</span>
          </div>
        </div>
        {user && user.role !== "Public" && (
          <div className="row">
            <button className="btn btn--primary btn--sm">
              <Icon name="upload" size={11} /> Upload
            </button>
          </div>
        )}
      </div>

      <div className="filterbar">
        <span className="filterbar__lab">Type</span>
        {([["all", "All"], ["image", "Images"], ["audio", "Audio"], ["pdf", "Documents"]] as [MediaFilter, string][]).map(([k, l]) => (
          <span
            key={k}
            className={`chip ${filter === k ? "is-active" : ""}`}
            onClick={() => setFilter(k)}
          >
            {l}
          </span>
        ))}
      </div>

      <div className="media-grid">
        {items.map((m) => (
          <article key={m.id} className="media-card">
            {m.type === "image" && <ImgHolder label={m.id} ratio="4/3" />}
            {m.type === "audio" && (
              <div className="imgholder" style={{ aspectRatio: "4/3" }}>
                <span><Icon name="audio" size={20} /> WAV · {m.size}</span>
              </div>
            )}
            {m.type === "pdf" && (
              <div className="imgholder" style={{ aspectRatio: "4/3" }}>
                <span><Icon name="pdf" size={20} /> PDF · {m.size}</span>
              </div>
            )}
            <div className="media-card__body">
              <div className="media-card__name">{m.filename}</div>
              <div className="media-card__cap">{m.caption}</div>
              <div className="media-card__meta">
                <span>{m.uploadedBy}</span>
                <span>{m.size} · {m.at}</span>
              </div>
              <div className="row" style={{ gap: 6, marginTop: 10 }}>
                <span className="tag mono">{m.page}</span>
                <span style={{ flex: 1 }} />
                <span className="mono xsmall muted">sha256 b3f…{m.id.slice(-3)}</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
