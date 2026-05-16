import { Topbar } from "@/components/shell/Topbar";
import { Sidebar } from "@/components/shell/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <Topbar />
      <div className="layout">
        <Sidebar />
        <main className="main">{children}</main>
      </div>
    </div>
  );
}
