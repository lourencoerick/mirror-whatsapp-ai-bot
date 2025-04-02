"use client";

import React, { createContext, useState, useContext, ReactNode, Dispatch, SetStateAction } from 'react';

interface LayoutContextProps {
  // --- Change type from string to ReactNode ---
  pageTitle: ReactNode;
  // --- Change setter type accordingly ---
  setPageTitle: Dispatch<SetStateAction<ReactNode>>;
}

// Default value can still be a string (string is a valid ReactNode)
const defaultContextValue: LayoutContextProps = {
  pageTitle: 'Dashboard', // Default title remains a string
  setPageTitle: () => {},
};

const LayoutContext = createContext<LayoutContextProps>(defaultContextValue);

interface LayoutProviderProps {
  children: ReactNode;
}

/**
 * Provides page title management context to its children.
 * The page title can be a string or any valid ReactNode (like a Link).
 */
export const LayoutProvider: React.FC<LayoutProviderProps> = ({ children }) => {
  // --- Change state type from string to ReactNode ---
  const [pageTitle, setPageTitle] = useState<ReactNode>('Dashboard'); // Initial value is a string

  return (
    <LayoutContext.Provider value={{ pageTitle, setPageTitle }}>
      {children}
    </LayoutContext.Provider>
  );
};

/**
 * Hook to easily consume the LayoutContext.
 */
export const useLayoutContext = () => {
  const context = useContext(LayoutContext);
  if (context === undefined) {
    throw new Error('useLayoutContext must be used within a LayoutProvider');
  }
  return context;
};