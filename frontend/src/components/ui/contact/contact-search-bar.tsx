"use client"; 

import React, { useState, useEffect, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';

/**
 * Props for the ContactSearchBar component.
 */
interface ContactSearchBarProps {
  /** Callback function triggered with the debounced search term. */
  onSearchChange: (term: string) => void;
  /** Optional placeholder text for the input field. */
  placeholder?: string;
  /** Optional initial value for the search bar. */
  initialValue?: string;
  /** Optional debounce delay in milliseconds. Defaults to 300ms. */
  debounceDelay?: number;
  /** Optional additional CSS classes for the container div. */
  className?: string;
}

/**
 * Renders a search input field with debouncing for contact searching.
 * Texts are in Brazilian Portuguese.
 *
 * @component
 * @param {ContactSearchBarProps} props - The component props.
 * @returns {React.ReactElement} The rendered search bar.
 */
const ContactSearchBar: React.FC<ContactSearchBarProps> = ({
  onSearchChange,
  placeholder = "Buscar contatos...", 
  initialValue = "",
  debounceDelay = 300,
  className = "",
}) => {
  const [inputValue, setInputValue] = useState<string>(initialValue);
  const [debouncedValue, setDebouncedValue] = useState<string>(initialValue);
  const isInitialMount = useRef(true);

  // Effect to handle debouncing
  useEffect(() => {
    const handler = setTimeout(() => {
      if (inputValue !== debouncedValue) {
          setDebouncedValue(inputValue);
      }
    }, debounceDelay);
    return () => {
      clearTimeout(handler);
    };
  }, [inputValue, debounceDelay, debouncedValue]);

  // Effect to call the callback function when the debounced value changes
  useEffect(() => {
    if (isInitialMount.current) {
        isInitialMount.current = false;
        if (initialValue === "") {
             onSearchChange(debouncedValue);
        }
        return;
    }
    onSearchChange(debouncedValue);
  }, [debouncedValue, onSearchChange, initialValue]);

  /**
   * Handles changes in the input field.
   * @param {React.ChangeEvent<HTMLInputElement>} event - The input change event.
   */
  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
  };

  return (
    <div className={`relative w-full ${className}`}>
      <Search
        className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <Input
        type="search"
        placeholder={placeholder} 
        value={inputValue}
        onChange={handleInputChange}
        className="pl-10 pr-4 py-2 w-full"
        aria-label="Buscar contatos" 
      />
    </div>
  );
};

export default ContactSearchBar;