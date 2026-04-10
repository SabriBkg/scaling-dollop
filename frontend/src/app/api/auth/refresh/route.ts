import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/**
 * Server-side token refresh route.
 *
 * Reads the httpOnly refresh cookie, sends it to the Django refresh endpoint,
 * and sets the new access token as an httpOnly cookie. The client never sees
 * the raw tokens.
 */
export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("safenet_refresh")?.value;

  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 });
  }

  try {
    const res = await fetch(`${API_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!res.ok) {
      const response = NextResponse.json({ error: "Refresh failed" }, { status: 401 });
      response.cookies.delete("safenet_access");
      response.cookies.delete("safenet_refresh");
      return response;
    }

    const { access } = await res.json();
    const isProduction = process.env.NODE_ENV === "production";
    const response = NextResponse.json({ ok: true });

    response.cookies.set("safenet_access", access, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      maxAge: 15 * 60,
      path: "/",
    });

    return response;
  } catch {
    return NextResponse.json({ error: "Refresh failed" }, { status: 502 });
  }
}
