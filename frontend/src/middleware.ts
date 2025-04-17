// middleware.ts
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

// Public routes (no auth)
const isPublicRoute = createRouteMatcher([
  '/sign-in(.*)',
  '/sign-up(.*)',
  '/beta',
]);

// Routes that require admin role
const isAdminRoute = createRouteMatcher([
  '/dashboard(.*)',
]);

export default clerkMiddleware(async (auth, req) => {
  const { userId } = await auth();

  // it is needed the full origin to construct absolute URLs
  const origin = req.nextUrl.origin;

  // 1) Logged-in user accessing sign-in/sign-up → redirect to '/'
  if (userId && isPublicRoute(req)) {
    const redirectUrl = new URL('/', req.url);
    return NextResponse.redirect(redirectUrl);
  }

  // 2) /dashboard/** routes: require admin role
  if (isAdminRoute(req)) {
    console.log(`Accessing admin route ${req.url}`);
    await auth.protect(
      // (has) => has({ role: 'admin' }),
      {
        unauthenticatedUrl: `${origin}/sign-in`,
        unauthorizedUrl:    `${origin}/pending-approval`,
      }
    );
  }
  // 3) All other non-public routes: require login only
  else if (!isPublicRoute(req)) {
    await auth.protect({
      unauthenticatedUrl: `${origin}/sign-in`,
    });
  }

  // 4) Continue as normal
  return NextResponse.next();
});

export const config = {
  matcher: [
    '/((?!_next|.*\\..*).*)',
    '/(api|trpc)(.*)',
  ],
};
