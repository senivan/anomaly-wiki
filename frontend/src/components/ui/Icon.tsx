interface IconProps {
  name: string;
  size?: number;
}

export function Icon({ name, size = 14 }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "search":   return <svg {...common}><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>;
    case "edit":     return <svg {...common}><path d="M3 21h18"/><path d="M5 17 17 5l3 3L8 20l-5 1 1-5z"/></svg>;
    case "plus":     return <svg {...common}><path d="M12 5v14M5 12h14"/></svg>;
    case "filter":   return <svg {...common}><path d="M3 5h18M6 12h12M10 19h4"/></svg>;
    case "image":    return <svg {...common}><rect x="3" y="3" width="18" height="18"/><circle cx="9" cy="9" r="2"/><path d="m21 16-5-5L5 21"/></svg>;
    case "audio":    return <svg {...common}><path d="M9 18V6l11-2v12"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/></svg>;
    case "pdf":      return <svg {...common}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg>;
    case "check":    return <svg {...common}><path d="M5 13l4 4L19 7"/></svg>;
    case "x":        return <svg {...common}><path d="M6 6l12 12M18 6 6 18"/></svg>;
    case "branch":   return <svg {...common}><circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="9" r="2"/><path d="M6 8v8M6 18c0-6 12-3 12-9"/></svg>;
    case "history":  return <svg {...common}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/></svg>;
    case "doc":      return <svg {...common}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h6"/></svg>;
    case "user":     return <svg {...common}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>;
    case "shield":   return <svg {...common}><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/></svg>;
    case "alert":    return <svg {...common}><path d="M12 3 2 21h20z"/><path d="M12 10v5M12 18h.01"/></svg>;
    case "arrow":    return <svg {...common}><path d="M5 12h14M13 5l7 7-7 7"/></svg>;
    case "external": return <svg {...common}><path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M20 14v6H4V4h6"/></svg>;
    case "link":     return <svg {...common}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 1 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 1 0 5.7 5.7l1-1"/></svg>;
    case "upload":   return <svg {...common}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;
    case "sun":      return <svg {...common}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>;
    case "moon":     return <svg {...common}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>;
    default: return null;
  }
}
