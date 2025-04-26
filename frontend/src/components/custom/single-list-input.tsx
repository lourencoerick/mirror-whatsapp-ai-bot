// components/custom/StringListInput.tsx
'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { X as RemoveIcon } from 'lucide-react'; // Import X icon
import React, { KeyboardEvent, useState } from 'react';
import { ControllerRenderProps, FieldError } from 'react-hook-form'; // Import types

interface StringListInputProps {
  // Props provided by react-hook-form Controller's render prop
  field: ControllerRenderProps<any, string>; // Field object from RHF Controller
  label: string;
  id: string;
  placeholder?: string;
  error?: FieldError; // Error object from RHF
}

export function StringListInput({
  field, // Contains value, onChange, name, etc.
  label,
  id,
  placeholder = 'Add item and press Enter or Add',
  error,
}: StringListInputProps) {
  // Internal state for the input field value
  const [inputValue, setInputValue] = useState<string>('');

  // Get the current list from the form state via the field prop
  const currentList: string[] = Array.isArray(field.value) ? field.value : [];

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(event.target.value);
  };

  const handleAddItem = () => {
    const newItem = inputValue.trim();
    if (newItem && !currentList.includes(newItem)) { // Add only if not empty and not duplicate
      const newList = [...currentList, newItem];
      field.onChange(newList); // Update react-hook-form state
      setInputValue(''); // Clear the input field
    } else if (newItem && currentList.includes(newItem)) {
        // Optional: Add feedback if item already exists (e.g., using sonner)
        console.warn(`Item "${newItem}" already exists in the list.`);
        setInputValue(''); // Still clear input
    } else {
        // Clear input even if empty
         setInputValue('');
    }
  };

  const handleRemoveItem = (indexToRemove: number) => {
    const newList = currentList.filter((_, index) => index !== indexToRemove);
    field.onChange(newList); // Update react-hook-form state
  };

  // Handle Enter key press in the input field
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault(); // Prevent default form submission on Enter
      handleAddItem();
    }
  };

  return (
    <div className="space-y-2">
      <Label className="mb-1.5 block" htmlFor={id}>{label}</Label>
      <div className="flex items-center space-x-2">
        <Input
          id={id}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown} // Add listener for Enter key
          placeholder={placeholder}
          className="flex-grow"
        />
        <Button type="button" onClick={handleAddItem} variant="outline">
          Add
        </Button>
      </div>
      {error && <p className="text-xs text-red-600 mt-1">{error.message}</p>}
      <div className="flex flex-wrap gap-2 mt-2">
        {currentList.map((item, index) => (
          <Badge key={index} variant="secondary" className="flex items-center">
            {item}
            <button
              type="button"
              onClick={() => handleRemoveItem(index)}
              className="ml-1.5 rounded-full outline-none ring-offset-background focus:ring-2 focus:ring-ring focus:ring-offset-2"
              aria-label={`Remove ${item}`}
            >
              <RemoveIcon className="h-3 w-3 text-muted-foreground hover:text-foreground" />
            </button>
          </Badge>
        ))}
        {currentList.length === 0 && (
             <p className="text-xs text-muted-foreground italic">No items added yet.</p>
        )}
      </div>
    </div>
  );
}