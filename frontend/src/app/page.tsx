// app/page.tsx
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

/**
 * @file Root page component for the application.
 * @description This server component handles initial redirection based on the user's
 * authentication status and admin role. It ensures users are directed
 * to the appropriate starting point.
 * @returns {Promise<null>} This component always redirects, so it returns null.
 */
export default async function RootPage() {
  const { userId, sessionClaims } = await auth();

  // If the user is not logged in, Clerk's middleware should generally handle redirection to /sign-in.
  // This check acts as a fallback or for scenarios where middleware might not cover the root path.
  if (!userId) {
    console.log("RootPage: No userId found, redirecting to /sign-in.");
    redirect("/sign-in");
  }

  // Check for admin role from sessionClaims metadata.
  // Ensure 'role' is defined in publicMetadata or privateMetadata in your Clerk dashboard settings.
  const role = (sessionClaims?.metadata as { role?: string })?.role;
  const isAdmin = role === "admin";

  if (isAdmin) {
    console.log(
      `RootPage: User ${userId} is admin. Redirecting to /admin/beta-requests.`
    );
    // Admins are redirected to the admin beta requests page.
    // Consider a general admin dashboard (e.g., /admin/dashboard) if more appropriate.
    redirect("/admin/beta-requests");
  } else {
    // Logged-in, non-admin users are redirected to the main dashboard.
    // Further logic (e.g., based on subscription or beta status) will be handled
    // by client components within the /dashboard route.
    console.log(
      `RootPage: User ${userId} is not admin. Redirecting to /dashboard.`
    );
    redirect("/dashboard");
  }

  return null;
}
