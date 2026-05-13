import type { PageStatus, Visibility } from "@/lib/api/types";

interface StatusPillProps {
  status: PageStatus;
  visibility?: Visibility;
}

export function StatusPill({ status, visibility }: StatusPillProps) {
  const cls =
    status === "Published" ? "status--published" :
    status === "Review"    ? "status--review"    :
    status === "Redacted"  ? "status--redacted"  :
    "status--draft";
  const intCls = visibility === "Internal" ? " status--internal" : "";
  return (
    <span className={`status ${cls}${intCls}`}>
      {status}{visibility === "Internal" ? " · Internal" : ""}
    </span>
  );
}
