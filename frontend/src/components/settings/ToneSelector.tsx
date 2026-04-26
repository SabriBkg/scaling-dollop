"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/lib/api";
import type { Account, ApiResponse, NotificationTone } from "@/types";

const TONES: ReadonlyArray<{ value: NotificationTone; label: string; description: string }> = [
  {
    value: "professional",
    label: "Professional",
    description: "Formal, direct. No contractions.",
  },
  {
    value: "friendly",
    label: "Friendly",
    description: "Warm and conversational.",
  },
  {
    value: "minimal",
    label: "Minimal",
    description: "Bare facts. Two sentences max.",
  },
];

interface ToneSelectorProps {
  account: Account;
  value: NotificationTone;
  onChange: (tone: NotificationTone) => void;
  disabled?: boolean;
  disabledHint?: string;
}

export function ToneSelector({
  account,
  value,
  onChange,
  disabled = false,
  disabledHint,
}: ToneSelectorProps) {
  const queryClient = useQueryClient();
  const [isSaving, setIsSaving] = useState(false);

  const handleChange = async (tone: NotificationTone) => {
    if (tone === value || isSaving) return;

    const previousAccount = account;
    onChange(tone);
    queryClient.setQueryData<Account>(["account", "me"], { ...account, notification_tone: tone });

    setIsSaving(true);
    try {
      const { data } = await api.post<ApiResponse<Account>>("/account/notification-tone/", { tone });
      queryClient.setQueryData(["account", "me"], data.data);
      queryClient.invalidateQueries({ queryKey: ["account", "me"] });
      toast.success(`Notification tone set to ${tone}`);
    } catch {
      onChange(previousAccount.notification_tone);
      queryClient.setQueryData(["account", "me"], previousAccount);
      toast.error("Failed to update tone. Please try again.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div>
      {disabled && disabledHint && (
        <p className="mb-2 text-xs text-[var(--text-secondary)]">{disabledHint}</p>
      )}
      <div className="space-y-3">
        {TONES.map((tone) => (
          <label
            key={tone.value}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 transition-colors ${
              value === tone.value
                ? "border-[var(--accent-active)] bg-[var(--accent-active)]/5"
                : "border-[var(--border)] hover:border-[var(--text-tertiary)]"
            } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
          >
            <input
              type="radio"
              name="notification_tone"
              value={tone.value}
              checked={value === tone.value}
              onChange={() => handleChange(tone.value)}
              disabled={disabled || isSaving}
              className="accent-[var(--accent-active)]"
            />
            <div>
              <span className="text-sm font-medium text-[var(--text-primary)]">
                {tone.label}
              </span>
              <p className="text-xs text-[var(--text-secondary)]">
                {tone.description}
              </p>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
