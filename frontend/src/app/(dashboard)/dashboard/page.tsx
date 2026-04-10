// Story 2.3 implements the full dashboard shell and navigation
// Story 2.2 implements the retroactive scan job
export default function DashboardPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg-base">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-text-primary mb-2">Your account is ready.</h1>
        <p className="text-text-secondary">SafeNet is scanning your last 90 days of payment data.</p>
      </div>
    </main>
  );
}
