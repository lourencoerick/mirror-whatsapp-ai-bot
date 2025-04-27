/* eslint-disable @typescript-eslint/no-explicit-any */
// components/custom/StringListInput.tsx
"use client";

import { X as RemoveIcon } from "lucide-react"; // Icon for removal
import React, { KeyboardEvent, useState } from "react";
import { ControllerRenderProps, FieldError } from "react-hook-form"; // RHF types
import { toast } from "sonner"; // For user feedback

// UI Components
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider, // Ensure TooltipProvider wraps the component
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Props for the StringListInput component.
 */
interface StringListInputProps {
  /** Field object provided by react-hook-form's Controller render prop. Expects a string array value. */
  field: ControllerRenderProps<any, string[]>; // Changed expected type to string[]
  /** The label text displayed above the input field. */
  label: string;
  /** Unique ID for the input element, used for accessibility and label association. */
  id: string;
  /** Placeholder text for the text input field. */
  placeholder?: string;
  /** Error object from react-hook-form, used to display validation errors. */
  error?: FieldError | any; // Allow 'any' for flexibility
}

/**
 * A custom input component for managing a list of strings (e.g., tags, keywords).
 * Allows users to type text, add it to a list (via Enter key or Add button),
 * and remove items. Displays items as badges with tooltips.
 * Integrates with react-hook-form.
 * @param {StringListInputProps} props - The component props.
 * @returns {JSX.Element} The rendered string list input component.
 */
export function StringListInput({
  field, // Contains value, onChange, name, etc. from RHF Controller
  label,
  id,
  placeholder = "Adicione um item e pressione Enter ou Adicionar", // Default placeholder in pt-BR
  error,
}: StringListInputProps): JSX.Element {
  // State for the current value in the text input field
  const [inputValue, setInputValue] = useState<string>("");

  // Ensure the field value managed by react-hook-form is always an array
  const currentList: string[] = Array.isArray(field.value) ? field.value : [];

  /** Handles changes in the text input field. */
  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
  };

  /** Adds the current input value as a new item to the list, preventing duplicates. */
  const handleAddItem = () => {
    const newItem = inputValue.trim();
    if (newItem) {
      // Check for duplicates (case-insensitive comparison)
      const isDuplicate = currentList.some(
        (item) => item.trim().toLowerCase() === newItem.toLowerCase()
      );

      if (!isDuplicate) {
        const newList = [...currentList, newItem];
        field.onChange(newList); // Update react-hook-form state
        setInputValue(""); // Clear the input field
      } else {
        // Provide user feedback if the item already exists
        toast.warning("Item já existe", {
          description: `O item "${newItem}" já está na lista.`,
        });
        setInputValue(""); // Still clear the input field
      }
    } else {
      setInputValue(""); // Clear input if it was empty or only whitespace
    }
  };

  /**
   * Removes an item from the list based on its index.
   * @param {number} indexToRemove - The index of the item to remove.
   */
  const handleRemoveItem = (indexToRemove: number) => {
    const newList = currentList.filter((_, index) => index !== indexToRemove);
    field.onChange(newList); // Update react-hook-form state
  };

  /** Handles the 'Enter' key press in the input field to add the item. */
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault(); // Prevent default form submission behavior
      handleAddItem();
    }
  };

  // Safely extract the error message string
  const errorMessage =
    typeof error?.message === "string" ? error.message : undefined;

  return (
    // TooltipProvider is necessary for Tooltip components to function
    <TooltipProvider delayDuration={300}>
      <div className="space-y-2">
        {/* Main label for the component */}
        <Label className="mb-1.5 block" htmlFor={id}>
          {label}
        </Label>
        {/* Row containing the Text Input and Add Button */}
        <div className="flex items-center space-x-2">
          <Input
            id={id} // Link input to the label
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown} // Add item on Enter key press
            placeholder={placeholder}
            className="flex-grow" // Allow input to take remaining space
            aria-invalid={!!error} // Indicate invalid state for accessibility
            aria-describedby={error ? `${id}-error` : undefined}
          />
          <Button
            type="button"
            onClick={handleAddItem}
            variant="outline"
            className="flex-shrink-0" // Prevent button from shrinking
          >
            Adicionar {/* Button text in pt-BR */}
          </Button>
        </div>

        {/* Display validation error message */}
        {errorMessage && (
          <p id={`${id}-error`} className="text-xs text-red-600 mt-1">
            {errorMessage}
          </p>
        )}

        {/* Container for displaying the list of items as badges */}
        <div className="flex flex-wrap gap-2 mt-2 min-h-[40px] max-h-40 overflow-y-auto rounded border p-2 bg-muted/50">
          {/* Sort list alphabetically for consistent display */}
          {[...currentList] // Create a copy before sorting
            .sort((a, b) => a.localeCompare(b))
            .map((item) => {
              const originalIndex = currentList.indexOf(item);
              return (
                <Tooltip key={originalIndex}>
                  <TooltipTrigger asChild>
                    {/* Badge serves as the trigger for the tooltip */}
                    <Badge
                      variant="secondary"
                      className="flex items-center max-w-full px-2 py-0.5 cursor-default"
                    >
                      {/* Span to truncate long text within the badge */}
                      <span className="block truncate max-w-[200px] sm:max-w-[300px] mr-1">
                        {item}
                      </span>
                      {/* Button to remove the item */}
                      <button
                        type="button"
                        onClick={() => handleRemoveItem(originalIndex)}
                        className="-mr-1 ml-1 rounded-full outline-none ring-offset-background focus:ring-2 focus:ring-ring focus:ring-offset-2 flex-shrink-0 p-0.5 hover:bg-background/50"
                        aria-label={`Remover ${item}`} // Aria label in pt-BR
                      >
                        <RemoveIcon className="h-3 w-3 text-muted-foreground group-hover:text-foreground" />{" "}
                        {/* Adjust icon color on hover if needed */}
                      </button>
                    </Badge>
                  </TooltipTrigger>
                  {/* Tooltip shows the full item text on hover */}
                  <TooltipContent side="top" align="start">
                    <p className="max-w-md break-words whitespace-pre-wrap">
                      {item}
                    </p>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          {/* Message displayed when the list is empty */}
          {currentList.length === 0 && (
            <p className="text-xs text-muted-foreground italic px-1 w-full">
              Nenhum item adicionado ainda. {/* Empty state in pt-BR */}
            </p>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
