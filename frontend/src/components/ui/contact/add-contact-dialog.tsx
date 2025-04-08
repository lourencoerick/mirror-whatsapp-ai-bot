// src/components/contacts/AddContactDialog.tsx

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from '@/components/ui/button'; 
import { PlusCircle } from 'lucide-react'; 
import { AddContactForm } from './add-contact-form'; 
import type { KeyedMutator } from 'swr'; 
import type { PaginatedContact } from '@/types/contact'; 

/**
 * Props for the AddContactDialog component.
 */
interface AddContactDialogProps {
  /** SWR mutate function to refresh the contact list. */
  mutate: KeyedMutator<PaginatedContact>;
  /** Optional: Custom trigger element. If not provided, uses a default button. */
  trigger?: React.ReactNode;
}

/**
 * Renders a dialog containing the form to add a new contact.
 * Manages the dialog's open/closed state.
 *
 * @component
 * @param {AddContactDialogProps} props - Component props.
 * @returns {React.ReactElement} The rendered dialog component.
 */
export const AddContactDialog: React.FC<AddContactDialogProps> = ({ mutate, trigger }) => {
  const [isOpen, setIsOpen] = useState(false);

  /**
   * Handles successful form submission.
   * Closes the dialog and triggers data refresh.
   */
  const handleSuccess = () => {
    setIsOpen(false); // Fecha o modal
    mutate(); // Revalida os dados SWR para atualizar a lista
  };

  /**
   * Handles closing the dialog manually (e.g., via cancel button or overlay click).
   * @param {boolean} open - The new open state provided by Dialog component.
   */
  const handleOpenChange = (open: boolean) => {
    // Reset form state if closing? Maybe not necessary if form resets on success.
    setIsOpen(open);
  };

  // Default trigger button if none is provided
  const defaultTrigger = (
    <Button className="w-full sm:w-auto">
      <PlusCircle className="mr-2 h-4 w-4" /> Adicionar Contato
    </Button>
  );

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger || defaultTrigger}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]"> {/* Adjust width as needed */}
        <DialogHeader>
          <DialogTitle>Adicionar Novo Contato</DialogTitle>
          <DialogDescription>
            Preencha as informações abaixo para criar um novo contato. O telefone é obrigatório.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <AddContactForm
             onSuccess={handleSuccess}
             onCancel={() => setIsOpen(false)} // Pass cancel handler
          />
        </div>
      </DialogContent>
    </Dialog>
  );
};