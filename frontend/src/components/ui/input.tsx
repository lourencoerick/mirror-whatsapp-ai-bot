import * as React from "react";
import { cn } from "@/lib/utils"; // Utility for merging class names

/**
 * Base Tailwind CSS classes for the Input component and variants.
 * Exported for use in other components needing consistent input styling.
 */
export const inputVariants = cn(
  // Base styles
  "flex h-9 w-full min-w-0 rounded-md border bg-transparent px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none",
  // File input specific styles
  "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground file:inline-flex file:h-7",
  // Placeholder styles
  "placeholder:text-muted-foreground",
  // Selection styles
  "selection:bg-primary selection:text-primary-foreground",
  // Dark mode styles (adjust if not using dark mode)
  "dark:bg-input/30",
  // Border styles
  "border-input",
  // Disabled state styles
  "disabled:cursor-not-allowed disabled:opacity-50 disabled:pointer-events-none",
  // Focus state styles
  "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
  // Invalid state styles (using aria-invalid)
  "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
  "dark:aria-invalid:ring-destructive/40",
  // Responsive text size (optional, adjust as needed)
  "md:text-sm"
);

/**
 * Props for the Input component, extending standard HTML input attributes.
 */
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

/**
 * A customizable input component applying consistent base styles.
 * @param {InputProps} props - The props for the input element.
 * @param {string} [props.className] - Additional classes to merge with base styles.
 * @param {string} [props.type] - The type of the input element.
 * @param {React.Ref<HTMLInputElement>} ref - Forwarded ref to the input element.
 * @returns {JSX.Element} The rendered input element.
 */
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        // Apply the base variants and merge any additional classes
        className={cn(inputVariants, className)}
        ref={ref}
        {...props}
        // data-slot attribute removed as it's less common and styling is handled by classes
      />
    );
  }
);
Input.displayName = "Input"; // For better debugging

export { Input };