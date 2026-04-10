import { NextRequest, NextResponse } from "next/server";

/**
 * Cookie bridge for Next.js middleware auth.
 *
 * Both access and refresh tokens are stored in httpOnly cookies — never in
 * localStorage. The middleware reads `safenet_access` to protect routes
 * server-side. The refresh cookie is sent to the refresh endpoint when needed.
 *
 * Story 2.3 implements the full login form UI that calls this route.
 */
export async function POST(request: NextRequest) {
  const { access, refresh } = await request.json();

  if (!access || !refresh) {
    return NextResponse.json({ error: "Missing tokens" }, { status: 400 });
  }

  const isProduction = process.env.NODE_ENV === "production";
  const response = NextResponse.json({ ok: true });

  response.cookies.set("safenet_access", access, {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax",
    maxAge: 15 * 60, // 15 minutes — matches JWT ACCESS_TOKEN_LIFETIME
    path: "/",
  });

  response.cookies.set("safenet_refresh", refresh, {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax",
    maxAge: 7 * 24 * 60 * 60, // 7 days — matches JWT REFRESH_TOKEN_LIFETIME
    path: "/",
  });

  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.delete("safenet_access");
  response.cookies.delete("safenet_refresh");
  return response;
}
