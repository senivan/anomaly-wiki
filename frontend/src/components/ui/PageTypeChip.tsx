import type { PageType } from "@/lib/api/types";

const TYPE_CLASS: Record<PageType, string> = {
  Anomaly:          "tag--danger",
  Artifact:         "tag--hazard",
  Location:         "",
  Incident:         "tag--danger",
  Expedition:       "tag--internal",
  "Researcher Note": "",
  Article:          "",
};

export function PageTypeChip({ type }: { type: PageType }) {
  return <span className={`tag ${TYPE_CLASS[type] ?? ""}`}>{type}</span>;
}
