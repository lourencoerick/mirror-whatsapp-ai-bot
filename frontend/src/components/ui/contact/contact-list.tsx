import React from 'react';
import { Contact } from '@/types/contact'; 
import ContactListItem from './contact-item'; 
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'; 
import { cn } from '@/lib/utils'; 

/**
 * Props for the ContactList component including sorting.
 */
interface ContactListProps {
  contacts: Contact[];
  isLoading: boolean;
  onEdit: (contactId: string) => void;
  onDelete: (contactId: string) => void;
  // --- Sorting Props ---
  sortBy: string | null;
  sortDirection: 'asc' | 'desc';
  onSortChange: (column: string) => void;
}

/**
 * Renders a list of contacts using ContactListItem.
 * Includes sortable headers, loading, and empty states.
 * Texts are in Brazilian Portuguese.
 *
 * @component
 * @param {ContactListProps} props - The component props.
 * @returns {React.ReactElement} The rendered contact list.
 */
const ContactList: React.FC<ContactListProps> = ({
  contacts,
  isLoading,
  onEdit,
  onDelete,
  sortBy,
  sortDirection,
  onSortChange,
}) => {

  /**
   * Helper component for rendering a sortable header cell.
   */
  const SortableHeader = ({ columnKey, label, className }: { columnKey: string, label: string, className?: string }) => {
    const isActive = sortBy === columnKey;
    const Icon = isActive ? (sortDirection === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;

    const directionText = isActive ? (sortDirection === 'asc' ? '(ascendente)' : '(descendente)') : '';

    return (
      <div
        className={cn(
            "flex items-center gap-1 cursor-pointer select-none hover:text-foreground transition-colors",
            className
        )}
        onClick={() => onSortChange(columnKey)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSortChange(columnKey); }}
        aria-label={`Ordenar por ${label} ${directionText}`} // Translated aria-label
      >
        {label} {/* Label is passed already translated */}
        <Icon
          className={cn("h-3 w-3 flex-shrink-0", isActive ? "text-foreground" : "text-muted-foreground/50")}
          aria-hidden="true"
        />
      </div>
    );
  };

  // Loading State: Display skeleton loaders
  if (isLoading) {
    return (
      <div className="border rounded-lg overflow-hidden mt-4">
        {/* Optional Header Skeleton */}
        <div className="hidden md:flex items-center bg-muted/50 border-b px-4 py-3">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-32 ml-4" />
            <Skeleton className="h-4 w-40 ml-auto" />
        </div>
        {/* Skeleton Items */}
        <div className="divide-y">
            {[...Array(5)].map((_, index) => (
            <div key={index} className="flex items-center py-3 px-4">
                <div className="flex-1 min-w-0 space-y-2 mr-4">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                </div>
                <div className="flex items-center space-x-2 ml-auto">
                <Skeleton className="h-8 w-8 rounded-md" />
                <Skeleton className="h-8 w-8 rounded-md" />
                </div>
            </div>
            ))}
        </div>
      </div>
    );
  }

  // Empty State: Display a message if no contacts and not loading
  if (!contacts || contacts.length === 0) {
    return (
      <div className="text-center py-10 border rounded-lg mt-4">
        <p className="text-gray-500">Nenhum contato encontrado.</p> 
        {/* Optional: Add a button/link here */}
      </div>
    );
  }

  // Data Available State: Render the list with sortable headers
  return (
    <div className="border rounded-lg overflow-hidden mt-4">
      {/* Header Row - Visible on medium screens and up */}
      <div className="hidden md:flex items-center bg-muted/50 border-b px-4 py-2 text-xs text-muted-foreground uppercase tracking-wider font-medium">
        {/* Ensure 'columnKey' matches the field name your backend uses for sorting */}
        <div className="flex-1 min-w-0 pr-4">
            <SortableHeader columnKey="name" label="Nome" /> 
        </div>
        <div className="w-48 pr-4">
            <SortableHeader columnKey="phone_number" label="Telefone" /> 
        </div>
        <div className="flex-1 min-w-0 pr-4">
            <SortableHeader columnKey="email" label="Email" /> 
        </div>
        {/* <div className="w-40 pr-4">
            <SortableHeader columnKey="created_at" label="Criado em" /> 
        </div> */}
        <div className="w-20 text-right flex-shrink-0">Ações</div> 
      </div>

      {/* Contact Items */}
      <div className="divide-y">
        {contacts.map((contact) => (
          <ContactListItem
            key={contact.id.toString()}
            contact={contact}
            onEdit={onEdit ? () => onEdit(contact.id.toString()) : undefined}
            onDelete={onDelete ? () => onDelete(contact.id.toString()) : undefined}
          />
        ))}
      </div>
    </div>
  );
};

export default ContactList;