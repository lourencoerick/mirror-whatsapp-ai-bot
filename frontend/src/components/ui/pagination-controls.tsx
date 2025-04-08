"use client";

import React from 'react';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * Props for the PaginationControls component.
 */
interface PaginationControlsProps {
  /** The currently active page number (1-based index). */
  currentPage: number;
  /** The total number of pages available. */
  totalPages: number;
  /** Callback function triggered when the user clicks Previous or Next. Receives the new target page number. */
  onPageChange: (page: number) => void;
  /** Optional: The total number of items across all pages. */
  totalItems?: number;
  /** Optional: The number of items displayed per page. */
  itemsPerPage?: number;
  /** Optional: Additional CSS classes for the container div. */
  className?: string;
}

/**
 * Renders pagination controls (Previous/Next buttons) and displays page/item information.
 *
 * @component
 * @param {PaginationControlsProps} props - The component props.
 * @returns {React.ReactElement | null} The rendered pagination controls, or null if totalPages <= 1.
 */
export const PaginationControls: React.FC<PaginationControlsProps> = ({
  currentPage,
  totalPages,
  onPageChange,
  totalItems,
  itemsPerPage,
  className = '', 
}) => {
  // Don't render controls if there's only one page or less, or if totalPages is invalid
  if (!totalPages || totalPages <= 1 || currentPage < 1 || currentPage > totalPages) {
    // Optionally log a warning in development for invalid props
    if (process.env.NODE_ENV === 'development' && (currentPage < 1 || currentPage > totalPages)) {
        console.warn(`PaginationControls: Invalid currentPage (${currentPage}) for totalPages (${totalPages}).`);
    }
    return null;
  }

  /** Handles clicking the 'Previous' button. */
  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  /** Handles clicking the 'Next' button. */
  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  // Calculate "Showing X-Y of Z" text if possible
  let showingText = '';
  if (totalItems !== undefined && itemsPerPage !== undefined && totalItems > 0 && itemsPerPage > 0) {
    const startIndex = Math.max((currentPage - 1) * itemsPerPage + 1, 1); 
    const endIndex = Math.min(currentPage * itemsPerPage, totalItems);
    showingText = `Showing ${startIndex}-${endIndex} of ${totalItems}`;
  } else if (totalItems !== undefined && totalItems > 0) {
    // Fallback if itemsPerPage is not provided but totalItems is
    showingText = `Total: ${totalItems}`;
  }

  return (
    <div className={`flex flex-col sm:flex-row items-center justify-between gap-2 py-2 px-4 text-sm text-muted-foreground ${className}`}>
      {/* Optional Showing Text (aligned left on larger screens) */}
      <div className="flex-1 text-center sm:text-left mb-2 sm:mb-0">
        {showingText ? (
            <span>{showingText}</span>
        ) : (
            // Render an empty span to maintain layout consistency if no text
            <span> </span>
        )}
      </div>

      {/* Pagination Buttons (aligned right on larger screens) */}
      <div className="flex items-center justify-center sm:justify-end space-x-2">
        <Button
          variant="outline"
          size="sm" // Use smaller buttons for pagination controls
          onClick={handlePrevious}
          disabled={currentPage === 1}
          aria-label="Go to previous page"
        >
          <ChevronLeft className="h-4 w-4" />
          {/* Optionally hide text on very small screens if needed */}
          <span className="ml-1 hidden xs:inline">Previous</span>
        </Button>

        <span className="font-medium px-2 whitespace-nowrap">
          Page {currentPage} of {totalPages}
        </span>

        <Button
          variant="outline"
          size="sm"
          onClick={handleNext}
          disabled={currentPage === totalPages}
          aria-label="Go to next page"
        >
           {/* Optionally hide text on very small screens if needed */}
          <span className="mr-1 hidden xs:inline">Next</span>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};