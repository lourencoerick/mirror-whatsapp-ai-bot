"use client";

import { Button } from '@/components/ui/button';

/**
 * A client component button that links to the application's sign-in page.
 * It constructs the URL using an environment variable.
 */
export function LoginButton() {
  // Construct the sign-in URL from the environment variable.
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://app.lambdalabs.com.br';
  const signInUrl = `${appUrl}/sign-in`;

  return (
    // The `asChild` prop passes the button's properties to its direct child (the `<a>` tag),
    // allowing the link to be styled exactly like a button.
    <Button asChild variant="outline">
      <a href={signInUrl}>
        Login
      </a>
    </Button>
  );
}