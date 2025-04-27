// components/custom/GuidelineInput.tsx
"use client";

import { X as RemoveIcon } from "lucide-react";
import React, { KeyboardEvent, useState } from "react";
import { ControllerRenderProps, FieldError } from "react-hook-form";
import { toast } from "sonner"; // For user notifications

// UI Components
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider, // Ensure TooltipProvider wraps the component
  TooltipTrigger,
} from "@/components/ui/tooltip";

// Defines the possible types for a guideline (using pt-BR terms internally and for display)
type GuidelineType = "BUSQUE" | "EVITE";

/**
 * Props for the GuidelineInput component.
 */
interface GuidelineInputProps {
  /** Field object provided by react-hook-form's Controller render prop. Expects a string array value. */
  field: ControllerRenderProps<any, string[]>;
  /** The label text displayed above the input field. */
  label: string;
  /** Unique ID for the input element, used for accessibility and label association. */
  id: string;
  /** Placeholder text for the text input field. */
  placeholder?: string;
  /** Error object from react-hook-form, used to display validation errors. */
  error?: FieldError | any; // Allow 'any' for flexibility if error structure varies
}

/**
 * A custom input component for managing a list of communication guidelines.
 * Allows users to select a type ('BUSQUE'/'EVITE'), enter text, add it to a list,
 * and remove items. Displays guidelines as colored badges with tooltips.
 * Integrates with react-hook-form.
 * @param {GuidelineInputProps} props - The component props.
 * @returns {JSX.Element} The rendered guideline input component.
 */
export function GuidelineInput({
  field,
  label,
  id,
  placeholder = "Digite o texto da diretriz...", // Default placeholder in pt-BR
  error,
}: GuidelineInputProps): JSX.Element {
  // State for the currently selected guideline type ('BUSQUE' or 'EVITE')
  const [guidelineType, setGuidelineType] = useState<GuidelineType>("BUSQUE");
  // State for the current value in the text input field
  const [inputValue, setInputValue] = useState<string>("");

  // Ensure the field value managed by react-hook-form is always an array
  const currentList: string[] = Array.isArray(field.value) ? field.value : [];

  /** Handles changes in the text input field. */
  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
  };

  /** Adds the current input value as a new guideline to the list. */
  const handleAddItem = () => {
    const text = inputValue.trim();
    if (text) {
      // Prepend the selected type to the guideline text
      const newItem = `${guidelineType} ${text}`;
      // Check for duplicates (case-insensitive, ignoring extra whitespace)
      const isDuplicate = currentList.some(
        (item) => item.trim().toLowerCase() === newItem.trim().toLowerCase()
      );

      if (!isDuplicate) {
        const newList = [...currentList, newItem];
        field.onChange(newList); // Update react-hook-form state
        setInputValue(""); // Clear the input field
        // Keep the selected type ('BUSQUE'/'EVITE') for easier multiple additions
      } else {
        // Show feedback if the guideline already exists
        toast.warning("Diretriz já existe", {
          description: "Esta diretriz já está na lista.",
        });
        setInputValue(""); // Clear input even if duplicate
      }
    } else {
      setInputValue(""); // Clear input if it was empty or only whitespace
    }
  };

  /**
   * Removes a guideline from the list based on its index.
   * @param {number} indexToRemove - The index of the guideline to remove.
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

        {/* Row containing the Type Select, Text Input, and Add Button */}
        <div className="flex items-center space-x-2">
          <Select
            value={guidelineType}
            onValueChange={(value: GuidelineType) => setGuidelineType(value)}
          >
            <SelectTrigger className="w-[110px] flex-shrink-0">
              {" "}
              {/* Slightly wider for pt-BR */}
              <SelectValue placeholder="Tipo" /> {/* Placeholder in pt-BR */}
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="BUSQUE">BUSQUE</SelectItem>
              <SelectItem value="EVITE">EVITE</SelectItem>
            </SelectContent>
          </Select>

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

        {/* Container for displaying the list of guidelines as badges */}
        <div className="flex flex-wrap gap-2 mt-2 min-h-[40px] max-h-48 overflow-y-auto rounded border p-2 bg-muted/50">
          {/* Sort list alphabetically for consistent display */}
          {[...currentList] // Create a copy before sorting to avoid mutating RHF state directly
            .sort((a, b) => a.localeCompare(b))
            .map((item) => {
              const originalIndex = currentList.indexOf(item);
              return (
                <Tooltip key={originalIndex}>
                  <TooltipTrigger asChild>
                    <Badge
                      variant={
                        item.startsWith("EVITE")
                          ? "dont"
                          : item.startsWith("BUSQUE")
                          ? "do"
                          : "default"
                      }
                      className="flex items-center max-w-full px-2 py-0.5 cursor-default"
                    >
                      <span className="block truncate max-w-[200px] sm:max-w-[300px] mr-1">
                        {item}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleRemoveItem(originalIndex)}
                        className="-mr-1 ml-1 rounded-full outline-none ring-offset-background focus:ring-2 focus:ring-ring focus:ring-offset-2 flex-shrink-0 p-0.5 hover:bg-background/50"
                        aria-label={`Remover ${item}`}
                      >
                        <RemoveIcon className="h-3 w-3" />
                      </button>
                    </Badge>
                  </TooltipTrigger>
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
              Nenhuma diretriz adicionada ainda.
            </p>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
