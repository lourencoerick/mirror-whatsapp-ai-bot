import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EditContactForm } from './edit-contact-form';
import type { KeyedMutator } from 'swr';
import type { PaginatedContact, Contact } from '@/types/contact';

/**
 * Props for the EditContactDialog component.
 */
interface EditContactDialogProps {
  /** The contact object to edit. If null, the dialog is closed. */
  contact: Contact | null;
  /** Function to call when the dialog should be closed (e.g., setting contact prop to null). */
  onClose: () => void;
  /** SWR mutate function to refresh the contact list. */
  mutate: KeyedMutator<PaginatedContact>;
}

/**
 * Renders a dialog containing the form to edit an existing contact.
 * The dialog's visibility is controlled by the presence of the 'contact' prop.
 *
 * @component
 * @param {EditContactDialogProps} props - Component props.
 * @returns {React.ReactElement | null} The rendered dialog component or null.
 */
export const EditContactDialog: React.FC<EditContactDialogProps> = ({ contact, onClose, mutate }) => {
  // Controla a abertura baseado na existência do 'contact'
  const isOpen = !!contact;

  /**
   * Handles successful form submission.
   * Closes the dialog and triggers data refresh.
   */
  const handleSuccess = () => {
    onClose(); // Chama a função para fechar (que deve setar contact para null no pai)
    mutate(); // Revalida os dados SWR
  };

  // Não renderiza nada se não houver contato para editar
  if (!isOpen || !contact) {
    return null;
  }

  return (
    // onOpenChange é usado para fechar via overlay click ou tecla Esc
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Editar Contato</DialogTitle>
          <DialogDescription>
            Modifique as informações do contato abaixo.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          {/* Passa o contato existente e os callbacks para o formulário */}
          <EditContactForm
             contact={contact}
             onSuccess={handleSuccess}
             onCancel={onClose}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
};