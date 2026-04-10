// Stub — Story 1.4 adds design token system and formatting utilities
export const formatCurrency = (cents: number, currency = "USD"): string => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
  }).format(cents / 100);
};

export const formatDate = (date: string | Date): string => {
  return new Intl.DateTimeFormat("en-US").format(new Date(date));
};
