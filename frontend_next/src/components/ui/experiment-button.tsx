import React from "react";
import Link from "next/link";
import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";

export type BetaSignupButtonProps = React.ComponentProps<typeof InteractiveHoverButton>;

export const BetaSignupButton = React.forwardRef<
  HTMLButtonElement,
  BetaSignupButtonProps
>(({ children, ...props }, ref) => {
  return (
    <Link href="/beta-signup" passHref>
      <InteractiveHoverButton ref={ref} {...props}>
        {children || "Começar agora"}
      </InteractiveHoverButton>
    </Link>
  );
});

BetaSignupButton.displayName = "BetaSignupButton";
