import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Public routes — no authentication required
const PUBLIC_PATHS = ["/login", "/register"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((path) => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Check for access token in cookie (set server-side on login via /api/auth/login route)
  // Note: localStorage is not accessible in middleware — use cookies for SSR auth check.
  // The axios interceptor in api.ts handles client-side refresh.
  const token = request.cookies.get("safenet_access")?.value;

  if (!token) {
    const registerUrl = new URL("/register", request.url);
    registerUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(registerUrl);
  }

  // Profile completion guard: authenticated users must complete their profile
  const profileComplete = request.cookies.get("safenet_profile_complete")?.value;
  if (!profileComplete) {
    const completeUrl = new URL("/register/complete", request.url);
    return NextResponse.redirect(completeUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|login|register).*)",
  ],
};
