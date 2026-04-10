/**
 * JWT authentication utilities.
 *
 * Tokens are stored exclusively in httpOnly cookies (set by /api/auth/login route).
 * Client-side JS cannot read the tokens directly — this is intentional for XSS protection.
 * The axios interceptor handles 401 by calling the server-side refresh endpoint.
 */

/**
 * Persist tokens by calling the cookie bridge route.
 * Both access and refresh tokens are set as httpOnly cookies server-side.
 */
export async function setTokens(access: string, refresh: string): Promise<void> {
  await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access, refresh }),
  });
}

/**
 * Clear auth cookies by calling the cookie bridge DELETE route.
 */
export async function clearTokens(): Promise<void> {
  await fetch("/api/auth/login", { method: "DELETE" });
}
