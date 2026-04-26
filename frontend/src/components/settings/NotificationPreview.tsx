"use client";

import { useNotificationPreview } from "@/hooks/useNotificationPreview";
import type { NotificationTone } from "@/types";

interface NotificationPreviewProps {
  tone: NotificationTone;
}

export function NotificationPreview({ tone }: NotificationPreviewProps) {
  const { data, isLoading, isError } = useNotificationPreview(tone);

  if (isLoading) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-4">
        <div className="h-4 w-1/3 animate-pulse rounded bg-[var(--border)]" />
        <div className="mt-4 h-[640px] animate-pulse rounded bg-[var(--border)]" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-4 text-sm text-[var(--text-secondary)]">
        Could not load preview. Please try again.
      </div>
    );
  }

  return (
    <div>
      <div className="rounded-t-lg border border-[var(--border)] bg-[var(--surface-sunken)] p-4">
        <p className="text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
          Subject
        </p>
        <p className="mt-1 text-sm font-medium text-[var(--text-primary)]">
          {data.subject}
        </p>
      </div>
      <iframe
        srcDoc={data.html_body}
        sandbox=""
        title="Email preview"
        className="h-[640px] w-full rounded-b-lg border border-t-0 border-[var(--border)] bg-white"
      />
      <p className="mt-2 text-xs text-[var(--text-secondary)]">
        Preview shown with sample subscriber data —{" "}
        <code>{data.sample_subscriber_email}</code>, decline code{" "}
        <code>{data.sample_decline_code}</code>.
      </p>
    </div>
  );
}
