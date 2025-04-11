// components/ui/contact/contact-item.tsx

import React from 'react';
import { Contact } from '@/types/contact';
import { Button } from '@/components/ui/button';
// Import the new icon
import { Trash2, Edit, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatPhoneNumber } from "@/lib/utils/phone-utils";

/**
 * Props for the ContactListItem component.
 */
interface ContactListItemProps {
  contact: Contact;
  onEdit?: (contactId: string) => void;
  onDelete?: (contactId: string) => void;
  onSendMessage?: () => void;
  onCardClick?: (contactId: string) => void;
}

/**
 * Renders a single contact item as a row with columns aligned
 * to the ContactList header (Name, Phone, Email, Actions).
 * Includes Edit, Delete, and Send Message actions.
 * Texts are in Brazilian Portuguese.
 *
 * @component
 * @param {ContactListItemProps} props - The component props.
 * @returns {React.ReactElement | null} The rendered contact item, or null if contact is invalid.
 */
const ContactListItem: React.FC<ContactListItemProps> = ({
  contact,
  onEdit,
  onDelete,
  onSendMessage,
  onCardClick,
}) => {
  if (!contact || !contact.id) {
    console.warn("ContactListItem: Invalid contact data provided.");
    return null;
  }

  const { id, name, phone_number, email } = contact;

  const contactIdentifier = name || phone_number || id.toString();
  const hasPhoneNumber = !!phone_number;

  const handleEditClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation(); // Prevent card click if applicable
    if (onEdit) {
      onEdit(id.toString());
    } else {
      console.warn("ContactListItem: onEdit handler not provided.");
    }
  };

  const handleDeleteClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation(); // Prevent card click if applicable
    if (onDelete) {
      onDelete(id.toString());
    } else {
      console.warn("ContactListItem: onDelete handler not provided.");
    }
  };

  // --- New Handler for Send Message ---
  const handleSendMessageClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation(); // Prevent card click if applicable
    if (onSendMessage && hasPhoneNumber) { 
      onSendMessage(); 
    } else if (!hasPhoneNumber) {
        console.warn("ContactListItem: Cannot send message, phone number missing.");
        // toast.warning("Contato sem número de telefone.");
    } else {
      console.warn("ContactListItem: onSendMessage handler not provided.");
    }
  };
  // --- End New Handler ---

  const handleCardClick = () => {
    if (onCardClick) {
      onCardClick(id.toString());
    }
  };

  const isCardClickable = !!onCardClick;

  return (
    <div
      className={cn(
        `group flex items-center py-3 px-4 border-b last:border-b-0 transition-colors`,
        isCardClickable ? 'cursor-pointer hover:bg-muted/50' : 'hover:bg-gray-50/50'
      )}
      onClick={isCardClickable ? handleCardClick : undefined}
      role={isCardClickable ? 'button' : undefined}
      tabIndex={isCardClickable ? 0 : undefined}
      aria-labelledby={`contact-name-${id}`}
      onKeyDown={isCardClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') handleCardClick(); } : undefined}
    >
      {/* --- Column Structure --- */}
      <div className="flex-1 min-w-0 pr-4">
        <p id={`contact-name-${id}`} className="text-sm font-medium text-gray-900 truncate">
          {name || 'Sem nome'}
        </p>
      </div>
      <div className="w-48 pr-4 hidden md:block">
        <p className="text-sm text-gray-500 truncate">
          {formatPhoneNumber(phone_number)}
        </p>
      </div>
      <div className="flex-1 min-w-0 pr-4 hidden md:block">
        {email ? (
          <p className="text-sm text-gray-500 truncate">{email}</p>
        ) : (
          <span className="text-sm text-gray-400 italic">Sem email</span>
        )}
      </div>

      <div className="w-auto md:w-28 flex items-center justify-end gap-0 sm:gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-within:opacity-100 transition-opacity flex-shrink-0">
        {/* Send Message Button */}
        {onSendMessage && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleSendMessageClick}
            disabled={!hasPhoneNumber} 
            aria-label={`Enviar mensagem para ${contactIdentifier}`}
            title={hasPhoneNumber ? `Enviar mensagem para ${contactIdentifier}` : "Contato sem número de telefone"} // Add title for clarity
            className="h-8 w-8"
          >
            <MessageSquare className="h-4 w-4" />
          </Button>
        )}
        {/* Edit Button */}
        {onEdit && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleEditClick}
            aria-label={`Editar contato ${contactIdentifier}`}
            className="h-8 w-8"
          >
            <Edit className="h-4 w-4" />
          </Button>
        )}
        {/* Delete Button */}
        {onDelete && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleDeleteClick}
            className="text-destructive hover:text-destructive/90 h-8 w-8"
            aria-label={`Excluir contato ${contactIdentifier}`}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )}
      </div>
      {/* --- End Column Structure --- */}
    </div>
  );
};

export default ContactListItem;