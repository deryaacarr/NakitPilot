import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { AUTH_COOKIE } from "@/lib/auth/constants";

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/customers",
  "/invoices",
  "/collections",
  "/promises",
  "/messages",
  "/forecast",
  "/imports",
  "/legal",
  "/offline",
] as const;

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  if (!isProtectedPath(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (token) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.search = "";
  loginUrl.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/dashboard",
    "/dashboard/:path*",
    "/customers",
    "/customers/:path*",
    "/invoices",
    "/invoices/:path*",
    "/collections",
    "/collections/:path*",
    "/promises",
    "/promises/:path*",
    "/messages",
    "/messages/:path*",
    "/forecast",
    "/forecast/:path*",
    "/imports",
    "/imports/:path*",
    "/legal",
    "/legal/:path*",
    "/offline",
  ],
};
