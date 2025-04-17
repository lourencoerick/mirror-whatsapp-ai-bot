// app/page.tsx
import { auth, currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

/**
 * Root page component.
 * Checks user authentication status and role.
 * Redirects admin users to the dashboard.
 * Redirects authenticated non-admin users to the pending approval page.
 * This page assumes it's protected by Clerk middleware for authenticated users.
 */
export default async function RootPage() {
  // Get authentication state server-side
  const { sessionClaims, userId } = await auth(); // Also get userId for logging if needed

  // If the user is not logged in, Clerk's middleware should handle this.
  if (!userId || !sessionClaims) {
     // This case should ideally be handled by your middleware redirecting to sign-in
     console.warn("RootPage accessed without authenticated user. Redirecting to /sign-in.");
     redirect('/sign-in');
  }

  const user = await currentUser();
  // Check for the 'admin' role in public metadata
  console.log(`User ${userId} session claims:`, sessionClaims);
  const isAdmin = user?.publicMetadata?.role === 'admin'

  if (isAdmin) {
    // User has the admin role, redirect to the main dashboard
    console.log(`User ${userId} is admin. Redirecting to /dashboard.`);
    redirect('/dashboard');
  } else {
    // User is logged in but not an admin, redirect to the pending approval page
    console.log(`User ${userId} is not admin. Redirecting to /pending-approval.`);
    redirect('/pending-approval');
  }

  // This part should technically be unreachable due to redirects
  return null;
}