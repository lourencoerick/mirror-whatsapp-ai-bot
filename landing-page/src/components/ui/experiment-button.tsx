"use client";

import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";
import React from "react";
import { Link as ScrollLink } from "react-scroll";

import { useRouter } from "next/navigation";

export type BetaSignupButtonProps = React.ComponentProps<typeof InteractiveHoverButton> & {
  "aria-label"?: string;
};

export const BetaSignupButton = React.forwardRef<
  HTMLButtonElement,
  BetaSignupButtonProps
>(({ children, "aria-label": ariaLabel, ...props }, ref) => {
  const router = useRouter();
  
  const handleClick = (href: string): void => {
      router.push(`/#${href}`);
  };

  return (
      <ScrollLink
        href="#pricing"
        activeClass="active"
        to="pricing"
        spy={true}
        smooth={true}
        offset={-50}
        duration={500}
        className="cursor-pointer"
        onClick={() => handleClick("pricing")}
        aria-label={ariaLabel || "Escolha um de nossos planos"}
      >
      <InteractiveHoverButton ref={ref} {...props}>
        {children || "Começar agora"}
      </InteractiveHoverButton>
    </ScrollLink>
  );
});

       

BetaSignupButton.displayName = "BetaSignupButton";
