import { NextResponse, type NextRequest } from "next/server";

/**
 * Edge routing only; this is not the security boundary. Every API call is authorised by
 * FastAPI using the httpOnly access cookie. `cf_signed_in` is a non-secret hint that lets us
 * redirect signed-out visitors before an app page renders.
 */
const SIGNED_IN = "cf_signed_in";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = request.cookies.get(SIGNED_IN)?.value === "1";

  // Public /analytics is a marketing page; signed-in users get their workspace analytics.
  if (pathname === "/analytics") {
    return signedIn ? NextResponse.rewrite(new URL("/workspace/analytics", request.url)) : NextResponse.next();
  }

  if (!signedIn) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/analytics",
    "/dashboard/:path*",
    "/content/:path*",
    "/calendar/:path*",
    "/media/:path*",
    "/agent/:path*",
    "/insights/:path*",
    "/intelligence/:path*",
    "/settings/:path*",
    "/onboarding/:path*",
    "/workspace/:path*",
    "/admin/:path*",
  ],
};
