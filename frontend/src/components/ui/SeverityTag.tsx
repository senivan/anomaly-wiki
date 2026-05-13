interface SeverityTagProps {
  value: string;
}

export function SeverityTag({ value }: SeverityTagProps) {
  const cls =
    value === "Lethal"     ? "tag--danger"   :
    value === "Severe"     ? "tag--hazard"   :
    value === "Restricted" ? "tag--internal" : "";
  return <span className={`tag ${cls}`}>Severity · {value}</span>;
}
