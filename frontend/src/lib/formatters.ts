export const formatCurrency = (cents: number, currency = "USD"): string => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(cents / 100);
};

export const formatDate = (date: string | Date): string => {
  return new Intl.DateTimeFormat("en-US").format(new Date(date));
};

export const formatRelativeTime = (date: string | Date): string => {
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

export const formatTimeUntil = (date: string | Date): string => {
  const seconds = Math.floor((new Date(date).getTime() - Date.now()) / 1000);
  if (seconds <= 0) return "overdue";
  if (seconds < 60) return "< 1m";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
};
