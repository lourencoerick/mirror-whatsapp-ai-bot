import React from "react";
import Link from "next/link";
import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";

interface BetaSignupButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {}

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
