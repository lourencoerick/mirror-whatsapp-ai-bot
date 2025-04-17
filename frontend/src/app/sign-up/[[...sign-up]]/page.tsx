// app/sign-up/[[...sign-up]]/page.tsx
import { SignUp } from "@clerk/nextjs";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign Up",
  description: "Create your account to get started.",
};

/**
 * Renders the sign-up page using Clerk's SignUp component.
 * The [[...sign-up]] route structure is recommended by Clerk
 * to handle all necessary sign-up flows.
 */
export default function SignUpPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignUp path="/sign-up" routing="path" signInUrl="/sign-in" />
    </div>
  );
}