// src/middleware.ts

import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Public routes (no auth)
const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"]);

// Admin-only routes
const isAdminRoute = createRouteMatcher(["/admin(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  const { userId, sessionClaims } = await auth();
  const origin = req.nextUrl.origin;
  const role = (sessionClaims?.metadata as { role?: string })?.role;

  // 1) Not logged in & not on a public route → redirect to sign-in
  if (!userId && !isPublicRoute(req)) {
    return NextResponse.redirect(new URL("/sign-in", origin));
  }

  // 2) Logged-in user on a public route → redirect to home
  if (userId && isPublicRoute(req)) {
    return NextResponse.redirect(new URL("/", origin));
  }

  // 3) Admin routes require "admin" role
  if (isAdminRoute(req)) {
    const isAdmin = role === "admin";
    await auth.protect(() => isAdmin, {
      unauthenticatedUrl: `${origin}/sign-in`,
      unauthorizedUrl: `${origin}/`, // or another "not authorized" page
    });
  }

  // 4) All other routes are allowed for any logged-in user
  return NextResponse.next();
});

export const config = {
  matcher: [
    // Match everything except _next static files and root file extensions
    "/((?!_next|.*\\..*).*)",
    "/(api|trpc)(.*)",
  ],
};
