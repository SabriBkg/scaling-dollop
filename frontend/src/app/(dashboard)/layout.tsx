import { NavBar } from "@/components/common/NavBar";
import { DashboardAttentionBar } from "@/components/dashboard/DashboardAttentionBar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--bg-base)]">
      <NavBar />
      <DashboardAttentionBar />
      <main className="mx-auto max-w-[1280px] px-8 py-6">
        {children}
      </main>
    </div>
  );
}
