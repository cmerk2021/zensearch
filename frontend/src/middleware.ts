import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  const backend = process.env.ZEN_BACKEND_URL || "http://localhost:8000";
  const { pathname, search } = request.nextUrl;
  return NextResponse.rewrite(`${backend}${pathname}${search}`);
}

export const config = {
  matcher: ["/api/v1/:path*", "/metrics"],
};
