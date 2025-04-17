import React from 'react';
// Removed: import { useRouter } from 'next/navigation';
import { Contact, PaginatedContact } from '@/types/contact'; // Ensure PaginatedContact is imported if needed by mutate type
import ContactListItem from './contact-item';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowDown, ArrowUp, ArrowUpDown, UserPlus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AddContactDialog } from './add-contact-dialog'; // *** Importado ***
import type { KeyedMutator } from 'swr'; // *** Importado para o tipo mutate ***

/**
 * Props for the ContactList component including sorting, actions, and data mutation.
 */
interface ContactListProps {
  contacts: Contact[];
  isLoading: boolean;
  onEdit: (contactId: string) => void;
  onDelete: (contactId: string) => void;
  onSendMessage: (contact: Contact) => void;
  // --- Sorting Props ---
  sortBy: string | null;
  sortDirection: 'asc' | 'desc';
  onSortChange: (column: string) => void;
  // --- Data Mutation Prop ---
  mutate: KeyedMutator<PaginatedContact>; // *** Adicionado: Função para revalidar dados ***
}

/**
 * Renders a list of contacts using ContactListItem.
 * Includes sortable headers, loading, empty states (with AddContactDialog trigger),
 * and passes action handlers down.
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
  onSendMessage,
  sortBy,
  sortDirection,
  onSortChange,
  mutate,
}) => {

  /**
   * Helper component for rendering a sortable header cell.
   */
  const SortableHeader = ({ columnKey, label, className }: { columnKey: string, label: string, className?: string }) => {
    // ... (código do SortableHeader permanece o mesmo) ...
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
        aria-label={`Ordenar por ${label} ${directionText}`}
      >
        {label}
        <Icon
          className={cn("h-3 w-3 flex-shrink-0", isActive ? "text-foreground" : "text-muted-foreground/50")}
          aria-hidden="true"
        />
      </div>
    );
  };

  // --- Empty State Trigger Button ---
  // Moved outside the main return for clarity, used in the Empty State section
  const EmptyStateTriggerButton = (
    <button
        // No onClick needed here, DialogTrigger handles it
        className="flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-border p-8 text-center hover:border-primary/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-colors"
        aria-label="Adicione seu primeiro contato"
    >
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mb-4">
            <UserPlus className="h-6 w-6 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-medium">Nenhum contato encontrado</h3>
        <p className="mt-1 text-sm text-muted-foreground">
            Comece adicionando seu primeiro contato.
        </p>
    </button>
  );


  // --- Main Render ---
  return (
    <div className="space-y-4"> {/* Added space-y for header and list separation */}
        {/* Loading State */}
        {isLoading && (
            <div className="border rounded-lg overflow-hidden">
                {/* Header Skeleton */}
                <div className="hidden md:flex items-center bg-muted/50 border-b px-4 py-3 text-xs">
                    <Skeleton className="h-4 w-20" /> {/* Nome */}
                    <Skeleton className="h-4 w-32 ml-4 flex-1" /> {/* Telefone */}
                    <Skeleton className="h-4 w-32 ml-4 flex-1" /> {/* Email */}
                    <Skeleton className="h-4 w-16 ml-auto" /> {/* Ações */}
                </div>
                {/* Items Skeleton */}
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
        )}

        {/* Empty State - Uses AddContactDialog with custom trigger */}
        {!isLoading && (!contacts || contacts.length === 0) && (
            <AddContactDialog mutate={mutate} trigger={EmptyStateTriggerButton} />
        )}

        {/* Data Available State */}
        {!isLoading && contacts && contacts.length > 0 && (
            <div className="border rounded-lg overflow-hidden">
                {/* Header Row */}
                <div className="hidden md:flex items-center bg-muted/50 border-b px-4 py-2 text-xs text-muted-foreground uppercase tracking-wider font-medium">
                    <div className="flex-1 min-w-0 pr-4">
                        <SortableHeader columnKey="name" label="Nome" />
                    </div>
                    <div className="w-48 pr-4">
                        <SortableHeader columnKey="phone_number" label="Telefone" />
                    </div>
                    <div className="flex-1 min-w-0 pr-4">
                        <SortableHeader columnKey="email" label="Email" />
                    </div>
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
                        onSendMessage={onSendMessage ? () => onSendMessage(contact) : undefined}
                    />
                    ))}
                </div>
            </div>
        )}
    </div>
  );
};

export default ContactList;