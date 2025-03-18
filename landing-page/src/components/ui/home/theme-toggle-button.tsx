'use client';

import { useTheme } from 'next-themes';
import { useState, useEffect } from 'react';
import { MoonIcon, SunIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

/**
 * Component to toggle the theme between "light" and "dark".
 */
export default function ThemeToggleButton() {
    const { theme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);
  
    useEffect(() => {
      setMounted(true);
    }, []);
  
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setTheme(theme === "light" ? "dark" : "light")}
        className="cursor-pointer"
        aria-label="Troca o tema de cor da página"
      >
        {mounted ? (
          theme === "light" ? <MoonIcon /> : <SunIcon />
        ) : (
          <div className="w-6 h-6" /> // Placeholder to 
        )}
      </Button>  
    );
  }