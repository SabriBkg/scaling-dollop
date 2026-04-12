import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

/**
 * API proxy that reads the httpOnly access cookie and forwards requests
 * to the Django backend with an Authorization: Bearer header.
 *
 * This bridges the gap between httpOnly cookie storage (XSS-safe) and
 * Django REST Framework's JWT authentication (expects Authorization header).
 *
 * When a backend response includes a `profile_complete` field, the proxy
 * sets or clears an httpOnly cookie so Next.js middleware can gate access
 * without a round-trip to the backend.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params);
}

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] }
) {
  const path = params.path.join("/");
  // Always append trailing slash — Django APPEND_SLASH=True rejects POST without it
  const url = `${BACKEND_URL}/${path}/${request.nextUrl.search}`;

  const headers: Record<string, string> = {};

  // Read httpOnly cookie and attach as Bearer token
  const accessToken = request.cookies.get("safenet_access")?.value;
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const fetchOptions: RequestInit = {
    method: request.method,
    headers,
  };

  // Forward body for non-GET requests
  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.text();
    if (body) {
      fetchOptions.body = body;
      headers["Content-Type"] = request.headers.get("Content-Type") ?? "application/json";
    }
  }

  const res = await fetch(url, fetchOptions);
  const body = await res.text();

  const response = new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });

  // Sync the profile_complete httpOnly cookie from backend response data.
  // This covers /auth/token/, /stripe/callback/, /account/complete-profile/, and /account/me/.
  if (res.ok) {
    try {
      const json = JSON.parse(body);
      const profileComplete = json?.data?.profile_complete ?? json?.profile_complete;
      if (typeof profileComplete === "boolean") {
        const isProduction = process.env.NODE_ENV === "production";
        if (profileComplete) {
          response.cookies.set("safenet_profile_complete", "true", {
            httpOnly: true,
            secure: isProduction,
            sameSite: "lax",
            maxAge: 365 * 24 * 60 * 60,
            path: "/",
          });
        } else {
          response.cookies.delete("safenet_profile_complete");
        }
      }
    } catch {
      // Non-JSON response — skip cookie sync
    }
  }

  return response;
}
