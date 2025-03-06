"use client"

import * as React from "react"
import Link from "next/link"
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu"


const sections = [
  { label: "Por que contratar Vendedor I.A.?", href: "/docs" },
  { label: "Como funciona", href: "/docs" },
  { label: "FAQ", href: "/docs" },
]

export function NavBarMenu() {
  return (
    <NavigationMenu>
      <NavigationMenuList>
        {sections.map((section) => (
          <NavigationMenuItem key={section.label}>
            <Link href={section.href} legacyBehavior passHref>
              <NavigationMenuLink className={navigationMenuTriggerStyle()}>
                {section.label}
              </NavigationMenuLink>
            </Link>
          </NavigationMenuItem>
        ))}
      </NavigationMenuList>
    </NavigationMenu>
  )
}

interface MobileNavBarMenuProps {
  onClose: () => void
}

export function MobileNavBarMenu({ onClose }: MobileNavBarMenuProps) {
  return (
    <div className="flex flex-col">
      {sections.map((section) => (
        <Link
          key={section.label}
          href={section.href}
          className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center"
          onClick={onClose}
        >
          {section.label}
        </Link>
      ))}
    </div>
  )
}
