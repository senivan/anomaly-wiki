interface StampProps {
  kind?: "approved" | "draft" | "redact";
  text: string;
}

export function Stamp({ kind = "approved", text }: StampProps) {
  const cls =
    kind === "draft"  ? "stamp stamp--draft"  :
    kind === "redact" ? "stamp stamp--redact" :
    "stamp";
  return <span className={cls} aria-hidden="true">{text}</span>;
}
