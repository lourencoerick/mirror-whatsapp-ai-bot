"use client"

import * as React from "react"
import Link from "next/link"

import { cn } from "@/lib/utils"
// import { Icons } from "@/components/icons"
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu"


export function NavBarMenu() {
  return (
    <NavigationMenu>
      <NavigationMenuList>
        <NavigationMenuItem>
          <Link href="/docs" legacyBehavior passHref>
            <NavigationMenuLink className={navigationMenuTriggerStyle()}>
              Como funciona
            </NavigationMenuLink>
          </Link>
        </NavigationMenuItem>

        <NavigationMenuItem>
          <Link href="/docs" legacyBehavior passHref>
            <NavigationMenuLink className={navigationMenuTriggerStyle()}>
              Benefícios
            </NavigationMenuLink>
          </Link>
        </NavigationMenuItem>

        <NavigationMenuItem>
          <Link href="/docs" legacyBehavior passHref>
            <NavigationMenuLink className={navigationMenuTriggerStyle()}>
              FAQ
            </NavigationMenuLink>
          </Link>
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
  )
}


interface MobileNavBarMenuProps {
  onClose: () => void;
}

export function MobileNavBarMenu({ onClose }: MobileNavBarMenuProps) {
  return (
    <div className="flex flex-col">
      <Link
        href="#hero"
        className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center"
        onClick={onClose}
      >
        Como funciona
      </Link>

      <Link
        href="#hero"
        className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center"
        onClick={onClose}
      >
        Benefícios
      </Link>

      <Link
        href="#hero"
        className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center"
        onClick={onClose}
      >
        FAQ
      </Link>            

    </div>
  );
}


