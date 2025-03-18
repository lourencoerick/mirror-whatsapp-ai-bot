"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Link as ScrollLink } from "react-scroll";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu";

type Section = {
  label: string;
  href: string;
};

const sections: Section[] = [
  { label: "Por que contratar Vendedor IA?", href: "beneficios" },
  { label: "Como funciona", href: "como-funciona" },
  { label: "FAQ", href: "faq" },
  { label: "Blog", href: "blog" },
];

const homeSectionsLabels: string[] = [
  "Por que contratar Vendedor IA?",
  "Como funciona",
  "FAQ",
];

export function NavBarMenu() {
  const router = useRouter();

  
  const handleClick = (section: Section): void => {
    if (homeSectionsLabels.includes(section.label)) {
      router.push(`/#${section.href}`);
    }
    else {
      router.push(`/${section.href}`);
    }
  };


  return (
    <NavigationMenu>
      <NavigationMenuList>
        {sections.map((section) => (
          <NavigationMenuItem key={section.label}>
            <ScrollLink
              activeClass="active"
              to={section.href}
              spy={true}
              smooth={true}
              offset={-50}
              duration={500}
              className={`${navigationMenuTriggerStyle()} cursor-pointer`}
              onClick={() => handleClick(section)}
            >
              {section.label}
            </ScrollLink>
          </NavigationMenuItem>
        ))}
      </NavigationMenuList>
    </NavigationMenu>
  );
}

interface MobileNavBarMenuProps {
  onClose: () => void;
}

export function MobileNavBarMenu({ onClose }: MobileNavBarMenuProps) {
  const router = useRouter();

  const handleClick = (section: Section): void => {
    if (homeSectionsLabels.includes(section.label)) {
      router.push(`/#${section.href}`);
    }
    else {
      router.push(`/${section.href}`);
    }
  };

  return (
    <div className="flex flex-col">
      {sections.map((section) => (
        <ScrollLink
          key={section.label}
          activeClass="active"
          to={section.href}
          spy={true}
          smooth={true}
          offset={-250}
          duration={500}
          className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center cursor-pointer"
          onClick={() => {
            handleClick(section);
            onClose();
          }}
        >
          {section.label}
        </ScrollLink>
      ))}
    </div>
  );
}
