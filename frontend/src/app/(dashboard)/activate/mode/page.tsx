// v1: mode selection is removed — see _bmad-output/sprint-change-proposal-2026-04-29.md. This page redirects.
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ModeSelectionPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);

  return (
    <div className="flex items-center justify-center py-20">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent-active)] border-t-transparent" />
    </div>
  );
}
