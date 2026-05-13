import type { ReactNode } from "react";
import { Icon } from "./Icon";

interface CalloutProps {
  tone?: "danger" | "warn" | "info";
  title: string;
  children: ReactNode;
}

export function Callout({ tone = "info", title, children }: CalloutProps) {
  const iconName = tone === "danger" ? "alert" : tone === "warn" ? "alert" : "shield";
  return (
    <div className={`callout callout--${tone}`}>
      <div className="callout__title">
        <Icon name={iconName} size={11} />
        {title}
      </div>
      <div>{children}</div>
    </div>
  );
}
