import { useState } from "react";
import api from "@/lib/api";

interface ConnectResult {
  oauth_url: string;
  state: string;
}

export function useStripeConnect() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initiateConnect = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.post<{ data: ConnectResult }>("/stripe/connect/");
      const { oauth_url } = response.data.data;
      window.location.href = oauth_url;
    } catch {
      setError("Failed to start Stripe connection. Please try again.");
      setLoading(false);
    }
  };

  return { initiateConnect, loading, error };
}
