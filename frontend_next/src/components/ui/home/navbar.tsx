'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { InteractiveHoverButton } from "@/components/magicui/interactive-hover-button";
import { NavBarMenu, MobileNavBarMenu } from "@/components/ui/home/navbar-menu"
import { Menu, X, MoonIcon, SunIcon } from 'lucide-react';
import { inter } from '@/components/ui/fonts';
import { useTheme } from 'next-themes';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { theme, setTheme } = useTheme();

  return (
    <header className="bg-background shadow-sm md:mt-2">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Main navigation container */}
        <div className="flex justify-between h-16 items-center">
          {/* Logo, vertical separator, and company name */}
          <Link href="/" className="flex items-center space-x-2">
            <Image
              src="/logo.png"
              alt="Lambda Labs"
              width={100}
              height={30}
              className="w-10 h-auto"
            />
            {/* Vertical separator */}
            <div className="h-8 border-l border-muted mx-2" />
            <span className={`${inter.className} text-2xl font-bold tracking-wide text-foreground`}>
              Lambda Labs
            </span>
          </Link>

          {/* Desktop navigation */}
          <div className="hidden md:flex items-center flex-grow">
            {/* Navigation sections */}
            <div className="flex space-x-6 flex-grow ml-4">
              <NavBarMenu />
            </div>

            {/* Buttons */}
            <div className="flex space-x-2 ml-8 items-center">
              <Link href="/login">
                <Button variant="outline" size="lg">
                  Login
                </Button>
              </Link>
              <Link href="/experimente">
                <InteractiveHoverButton>
                  Começar Agora
                </InteractiveHoverButton>
              </Link>

              {/* <div className="mt-8 flex justify-center md:justify-start"> */}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setTheme(theme === "light" ? "dark" : "light")}
                >
                  {theme === "light" ? (
                    <MoonIcon />
                  ) : (
                    <SunIcon  />
                  )}
                </Button>
              {/* </div> */}
            </div>
          </div>



          {/* Mobile menu button */}
          <div className="flex md:hidden">
            <Button variant="ghost" size="sm" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X className="h-8 w-8" /> : <Menu className="h-8 w-8" />}
            </Button>
          </div>
        </div>
      </nav>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <nav className="md:hidden bg-background border-t border-muted">
          <div className="pt-2 pb-3 space-y-1 ">
            <MobileNavBarMenu onClose={() => setMobileMenuOpen(false)} />
          </div>

          {/* Mobile buttons */}
          <div className="pt-4 pb-3 border-t border-muted">
            <div className="px-4 space-y-2">
              <Link href="/login" onClick={() => setMobileMenuOpen(false)} className="block">
                <Button variant="outline" size="sm" className="w-full">
                  Login
                </Button>
              </Link>
              <Link href="/experimente" onClick={() => setMobileMenuOpen(false)} className="block">
                <InteractiveHoverButton size="sm" className="w-full">
                  Experimente Agora
                </InteractiveHoverButton>
              </Link>
            </div>
          </div>

        </nav>
      )}
    </header>
  );
}
