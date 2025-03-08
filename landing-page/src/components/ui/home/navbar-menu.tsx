"use client"

import * as React from "react"
import { Link as ScrollLink } from "react-scroll";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu"


const sections = [
  { label: "Por que contratar Vendedor IA?", href: "beneficios" },
  { label: "Como funciona", href: "como-funciona" },
  { label: "FAQ", href: "faq" },
]

export function NavBarMenu() {
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
              offset={-50} // ajuste se tiver header fixo
              duration={500}
              className="cursor-pointer"

            >
              <NavigationMenuLink className={navigationMenuTriggerStyle()}>
                {section.label}
              </NavigationMenuLink>
            </ScrollLink>
          </NavigationMenuItem>
        ))}
      </NavigationMenuList>
    </NavigationMenu >
  )
}

interface MobileNavBarMenuProps {
  onClose: () => void
}

export function MobileNavBarMenu({ onClose }: MobileNavBarMenuProps) {
  return (
    <div className="flex flex-col">
      {sections.map((section) => (
        <ScrollLink
          key={section.label}
          activeClass="active"
          to={section.href}
          spy={true}
          smooth={true}
          offset={-250} // ajuste se tiver header fixo
          duration={500}
          className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center cursor-pointer"
          onClick={onClose}>
          {section.label}
        </ScrollLink>
      ))}
    </div>
  )
}
