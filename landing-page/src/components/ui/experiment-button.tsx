import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";
import Link from "next/link";
import React from "react";

export type BetaSignupButtonProps = React.ComponentProps<typeof InteractiveHoverButton> & {
  "aria-label"?: string;
};

export const BetaSignupButton = React.forwardRef<
  HTMLButtonElement,
  BetaSignupButtonProps
>(({ children, "aria-label": ariaLabel, ...props }, ref) => {
  return (
    <Link href="/beta" passHref aria-label={ariaLabel || "Inscreva-se para o Beta"}>
      <InteractiveHoverButton ref={ref} {...props}>
        {children || "Começar agora"}
      </InteractiveHoverButton>
    </Link>
  );
});

BetaSignupButton.displayName = "BetaSignupButton";
