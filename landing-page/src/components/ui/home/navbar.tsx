'use client';

import { Button } from '@/components/ui/button';
import { BetaSignupButton } from "@/components/ui/experiment-button";
import { inter } from '@/components/ui/fonts';
import { MobileNavBarMenu, NavBarMenu } from "@/components/ui/home/navbar-menu";
import ThemeToggleButton from "@/components/ui/home/theme-toggle-button";
import siteMetadata from '@/data/siteMetadata';
import { Menu, X } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { LoginButton } from './login-button'; // 1. Import the new LoginButton

export default function Navbar({ hideSignupButton = false }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 backdrop-blur bg-background shadow-sm md:mt-2">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Main navigation container */}
        <div className="flex justify-between h-16 items-center">
          {/* Logo, vertical separator, and company name */}
          <Link href="/" className="flex items-center space-x-2">
            <Image
              src="/logo.png"
              alt={`Logo da ${siteMetadata.headerTitle}`}
              width={100}
              height={30}
              className="w-10 h-auto"
            />
            <div className="h-8 border-l border-muted mx-2" />
            <span className={`${inter.className} text-lg sm:text-2xl font-bold tracking-wide text-foreground`}>
              {`${siteMetadata.headerTitle}`}
            </span>
          </Link>

          {/* Desktop navigation */}
          <div className="hidden lg:flex items-center flex-grow">
            <div className="flex space-x-6 flex-grow ml-4">
              <NavBarMenu />
            </div>

            {/* Desktop Buttons */}
            <div className="flex space-x-2 ml-8 items-center">
              <LoginButton /> {/* 2. Add LoginButton to the desktop view */}
              {!hideSignupButton && <BetaSignupButton />}
              <ThemeToggleButton />
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="flex lg:hidden items-center gap-x-4">
            {!hideSignupButton && <BetaSignupButton className="hidden sm:block" />}
            <ThemeToggleButton />
            <Button variant="ghost" size="sm" onClick={() => setMobileMenuOpen(!mobileMenuOpen)} aria-label="Expande o menu">
              {mobileMenuOpen ? <X className="h-8 w-8" /> : <Menu className="h-8 w-8" />}
            </Button>
          </div>
        </div>
      </nav>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <nav className="lg:hidden bg-background border-t border-muted">
          <div className="pt-2 pb-3 space-y-1">
            <MobileNavBarMenu onClose={() => setMobileMenuOpen(false)} />
          </div>

          {/* Mobile buttons */}
          <div className="pt-4 pb-3 border-t border-muted">
            <div className="px-4 flex flex-col space-y-2">
              <LoginButton /> {/* 3. Add LoginButton to the expanded mobile menu */}
              {!hideSignupButton && (
                <BetaSignupButton
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full" // Changed from block to w-full for consistency
                />
              )}
            </div>
          </div>
        </nav>
      )}
    </header>
  );
}