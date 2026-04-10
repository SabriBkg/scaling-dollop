import { NavBar } from "@/components/common/NavBar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[var(--bg-base)]">
      <NavBar />
      <main className="mx-auto max-w-[1280px] px-8 py-6">
        {children}
      </main>
    </div>
  );
}
