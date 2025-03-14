'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { NavBarMenu, MobileNavBarMenu } from "@/components/ui/home/navbar-menu";
import { Menu, X } from 'lucide-react';
import { inter } from '@/components/ui/fonts';
import { BetaSignupButton } from "@/components/ui/experiment-button";
import ThemeToggleButton  from "@/components/ui/home/theme-toggle-button"
import siteMetadata from '@/data/siteMetadata';


export default function Navbar() {
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
            {/* Vertical separator */}
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

            {/* Buttons */}
            <div className="flex space-x-2 ml-8 items-center">
              <BetaSignupButton />
              <ThemeToggleButton />
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="flex lg:hidden items-center gap-x-4">
            <BetaSignupButton className='hidden sm:block' />
            <ThemeToggleButton />
            <Button variant="ghost" size="sm" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
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
            <div className="px-4 space-y-2">
              <BetaSignupButton onClick={() => setMobileMenuOpen(false)} className="block w-full sm:hidden" />
            </div>
          </div>
        </nav>
      )}
    </header>
  );
}
