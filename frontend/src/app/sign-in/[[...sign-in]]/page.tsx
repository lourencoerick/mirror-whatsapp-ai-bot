// app/sign-in/[[...sign-in]]/page.tsx
import { SignIn } from "@clerk/nextjs";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign In",
  description: "Sign in to access your account.",
};

/**
 * Renders the Clerk Sign In component page.
 * Uses Clerk's built-in UI for user authentication.
 */
export default function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn path="/sign-in" routing="path" signUpUrl="/sign-up" />
    </div>
  );
}