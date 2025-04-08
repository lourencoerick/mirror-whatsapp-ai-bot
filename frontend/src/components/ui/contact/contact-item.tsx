import React from 'react';
import { Contact } from '@/types/contact'; 
import { Button } from '@/components/ui/button';
import { Trash2, Edit } from 'lucide-react';
import { cn } from '@/lib/utils'; 
import { formatPhoneNumber } from "@/lib/utils/phone-utils"; 

/**
 * Props for the ContactListItem component.
 */
interface ContactListItemProps {
  contact: Contact;
  onEdit?: (contactId: string) => void;
  onDelete?: (contactId: string) => void;
  onCardClick?: (contactId: string) => void;
}

/**
 * Renders a single contact item as a row with columns aligned
 * to the ContactList header (Name, Phone, Email, Actions).
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
  onCardClick,
}) => {
  if (!contact || !contact.id) {
    // Keep developer warnings in English for consistency
    console.warn("ContactListItem: Invalid contact data provided.");
    return null;
  }

  const { id, name, phone_number, email } = contact;

  const handleEditClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (onEdit) {
      onEdit(id.toString());
    } else {
      console.warn("ContactListItem: onEdit handler not provided.");
    }
  };

  const handleDeleteClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (onDelete) {
      onDelete(id.toString());
    } else {
      console.warn("ContactListItem: onDelete handler not provided.");
    }
  };

  const handleCardClick = () => {
    if (onCardClick) {
      onCardClick(id.toString());
    }
  };

  const isCardClickable = !!onCardClick;

  // Determine display name for aria-labels
  const contactIdentifier = name || phone_number;

  return (
    // Main row container - Apply group for hover effects
    <div
      className={cn(
        `group flex items-center py-3 px-4 border-b last:border-b-0 transition-colors`,
        isCardClickable ? 'cursor-pointer hover:bg-muted/50' : 'hover:bg-gray-50'
      )}
      onClick={isCardClickable ? handleCardClick : undefined}
      role={isCardClickable ? 'button' : undefined}
      tabIndex={isCardClickable ? 0 : undefined}
      aria-labelledby={`contact-name-${id}`}
      onKeyDown={isCardClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') handleCardClick(); } : undefined}
    >
      {/* --- Column Structure (Mirrors ContactList Header) --- */}

      {/* Name Column */}
      <div className="flex-1 min-w-0 pr-4">
        <p
          id={`contact-name-${id}`}
          className="text-sm font-medium text-gray-900 truncate"
        >
          {name || 'Sem nome'} {/* Translated */}
        </p>
      </div>

      {/* Phone Column */}
      <div className="w-48 pr-4 hidden md:block">
        <p className="text-sm text-gray-500 truncate">
          {formatPhoneNumber(phone_number)}
        </p>
      </div>

      {/* Email Column */}
      <div className="flex-1 min-w-0 pr-4 hidden md:block">
        {email ? (
          <p className="text-sm text-gray-500 truncate">{email}</p>
        ) : (
          <span className="text-sm text-gray-400 italic">Sem email</span> 
        )}
      </div>

      {/* Actions Column - Visible on hover/focus */}
      <div className="w-20 flex items-center justify-end gap-1 sm:gap-2 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-within:opacity-100 transition-opacity flex-shrink-0">
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
         {!onEdit && !onDelete && <div className="h-8 w-8"></div>}
      </div>
      {/* --- End Column Structure --- */}
    </div>
  );
};

export default ContactListItem;