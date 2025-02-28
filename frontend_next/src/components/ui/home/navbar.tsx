'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ExperimentButton } from '@/components/ui/icon-button';
import { Menu, X } from 'lucide-react';
import { inter } from '@/components/ui/fonts';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="bg-background shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
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
          <div className="hidden md:flex items-center ml-auto">
            {/* Navigation sections */}
            <div className="flex space-x-6">
              <Link href="#hero" className="text-sm font-medium text-foreground hover:text-muted-foreground">
                Hero Section
              </Link>
              <Link href="#beneficios" className="text-sm font-medium text-foreground hover:text-muted-foreground">
                Benefícios
              </Link>
              <Link href="#produto" className="text-sm font-medium text-foreground hover:text-muted-foreground">
                Produto
              </Link>
            </div>

            {/* Buttons */}
            <div className="flex space-x-2 ml-8">
              <Link href="/login">
                <Button variant="outline" size="lg">
                  Login
                </Button>
              </Link>
              <Link href="/experimente">
                <ExperimentButton variant="default" size="lg">
                  Experimente Agora
                </ExperimentButton>
              </Link>
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden">
            <Button variant="ghost" size="sm" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </Button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-background border-t border-muted">
          <div className="pt-2 pb-3 space-y-1">
            <Link
              href="#hero"
              className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center"
              onClick={() => setMobileMenuOpen(false)}
            >
              Hero Section
            </Link>
            <Link
              href="#beneficios"
              className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center"
              onClick={() => setMobileMenuOpen(false)}
            >
              Benefícios
            </Link>
            <Link
              href="#produto"
              className="block px-4 py-2 text-base font-medium text-foreground hover:bg-muted text-center"
              onClick={() => setMobileMenuOpen(false)}
            >
              Produto
            </Link>
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
                <Button variant="default" size="sm" className="w-full">
                  Experimente Agora
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
