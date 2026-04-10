"use client";

import { useRouter } from "next/navigation";
import { LogOut, Settings } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { clearTokens } from "@/lib/auth";
import { ROUTES } from "@/lib/constants";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function UserAvatar({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");

  return (
    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-medium text-[var(--text-secondary)] ring-1 ring-[var(--sn-border)]">
      {initials || "?"}
    </div>
  );
}

export function UserMenu() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  const displayName = user
    ? `${user.first_name} ${user.last_name}`.trim() || user.email
    : "";

  const handleLogout = async () => {
    try {
      await clearTokens();
    } finally {
      clearAuth();
      router.push(ROUTES.LOGIN);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-[var(--bg-elevated)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-active)]"
        aria-label="User menu"
      >
        <UserAvatar name={displayName} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {displayName && (
          <>
            <div className="px-2 py-1.5 text-xs text-[var(--text-secondary)]">
              {displayName}
            </div>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onClick={() => router.push(ROUTES.SETTINGS)}>
          <Settings className="mr-2 h-4 w-4" />
          Account settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout}>
          <LogOut className="mr-2 h-4 w-4" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
