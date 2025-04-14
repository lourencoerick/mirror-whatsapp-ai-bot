'use client';

import React, { useState, useEffect, useRef } from 'react';
import useSWR from 'swr';
import { Loader2, X } from 'lucide-react';
import { useDebounce } from 'use-debounce';

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useInboxes } from "@/hooks/use-inboxes";
import { useAuthenticatedFetch, FetchFunction } from '@/hooks/use-authenticated-fetch';
import { searchContacts } from '@/lib/api/contact';
import { Contact } from '@/types/contact';
import { useOnClickOutside } from '@/hooks/use-on-click-outside'; // Assuming you have this hook
import {formatPhoneNumber} from "@/lib/utils/phone-utils"
interface StartConversationFormProps {
  onStartConversation: (phoneNumber: string, inboxId: string) => Promise<void>;
  submitText?: string;
  loadingText?: string;
  initialContact?: Contact | null;
}

export function StartConversationForm({
  onStartConversation,
  submitText = "Iniciar Conversa",
  loadingText = "Iniciando...",
  initialContact = null, 
}: StartConversationFormProps) {
  const [searchQuery, setSearchQuery] = useState('');
  // Initialize selectedContact with initialContact if provided
  const [selectedContact, setSelectedContact] = useState<Contact | null>(initialContact);
  const [selectedInboxId, setSelectedInboxId] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  const [debouncedSearchQuery] = useDebounce(searchQuery, 300);
  const authenticatedFetch = useAuthenticatedFetch();
  const { inboxes, loading: inboxesLoading, error: inboxesError } = useInboxes();
  const searchContainerRef = useRef<HTMLDivElement>(null);

  useOnClickOutside(searchContainerRef, () => setIsDropdownOpen(false));

  // Effect to update selectedContact if initialContact changes (e.g., dialog reopens with different contact)
  useEffect(() => {
    setSelectedContact(initialContact);
    // Clear search when an initial contact is set
    if (initialContact) {
        setSearchQuery('');
    }
  }, [initialContact]);

  // --- SWR Fetcher for Contact Search (only runs if no initialContact) ---
  const searchFetcher = (
    query: string,
    fetchFn: FetchFunction
  ): Promise<Contact[]> => {
    if (!query || initialContact) return Promise.resolve([]);
    return searchContacts(query, 10, fetchFn);
  };

  const {
    data: searchResults,
    error: searchError,
    isLoading: isSearching,
  } = useSWR<Contact[], Error>(
    // Only trigger SWR if no initialContact and query exists
    !initialContact && debouncedSearchQuery ? [debouncedSearchQuery, 'searchContacts'] : null,
    ([query]) => searchFetcher(query, authenticatedFetch),
    { keepPreviousData: true }
  );

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    // Use selectedContact directly as it's updated by initialContact or selection
    if (!selectedContact || !selectedInboxId || isSubmitting) {
      console.warn("Please select a contact and an inbox.");
      return;
    }
    setIsSubmitting(true);
    try {
      if (!selectedContact.phone_number) {
          throw new Error("Contato selecionado não possui número de telefone.");
      }
      await onStartConversation(selectedContact.phone_number, selectedInboxId);
    } catch (error) {
      console.error("Submission failed in form:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleContactSelect = (contact: Contact) => {
    setSelectedContact(contact);
    setSearchQuery('');
    setIsDropdownOpen(false);
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    // Should not happen if initialContact is set, but safe guard
    if (initialContact) return;
    setSearchQuery(event.target.value);
    setSelectedContact(null);
    if (!isDropdownOpen) {
        setIsDropdownOpen(true);
    }
  };

  const handleFocus = () => {
    // Don't open dropdown if contact is pre-filled
    if (!initialContact) {
        setIsDropdownOpen(true);
    }
  };


  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Inbox Selector (remains the same) */}
      <div className="space-y-1">
        <Label htmlFor="inbox-select">Caixa de Entrada</Label>
        <Select
          value={selectedInboxId}
          onValueChange={setSelectedInboxId}
          disabled={inboxesLoading || isSubmitting}
          required
        >
          <SelectTrigger id="inbox-select">
            <SelectValue placeholder="Selecione uma caixa de entrada..." />
          </SelectTrigger>
          <SelectContent>
            {/* ... inbox options ... */}
             {inboxesLoading && <SelectItem value="loading" disabled>Carregando...</SelectItem>}
            {inboxesError && <SelectItem value="error" disabled>Erro ao carregar</SelectItem>}
            {!inboxesLoading && inboxes.length === 0 && <SelectItem value="empty" disabled>Nenhuma caixa disponível</SelectItem>}
            {inboxes.map((inbox) => (
              <SelectItem key={inbox.id} value={inbox.id}>
                {inbox.name} ({inbox.channel_type})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {!selectedInboxId && <p className="text-xs text-destructive">Selecione uma caixa de entrada.</p>}
      </div>

      {/* Contact Display/Search Area */}
      <div className="space-y-1">
        <Label htmlFor="contact-search">Contato</Label>
        {/* Always show selected contact info if initialContact is provided */}
        {selectedContact ? (
            <div className={cn(
                "flex items-center justify-between p-2 border rounded-md text-sm",
                initialContact ? "bg-muted/60" : "bg-muted/50"
            )}>
                <div>
                    <span className="font-medium">{selectedContact.name || 'Sem Nome'}</span>
                    <span className="ml-2 text-muted-foreground">({formatPhoneNumber(selectedContact.phone_number)})</span>
                </div>
                {/* Only show clear button if NOT pre-filled */}
                {!initialContact && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => setSelectedContact(null)}
                        aria-label="Limpar seleção de contato"
                        disabled={isSubmitting}
                    >
                        <X className="h-4 w-4" />
                    </Button>
                )}
            </div>
        ) : (
            /* Search input and dropdown container (only shown if no initialContact) */
            <div className="relative" ref={searchContainerRef}>
                <Input
                    id="contact-search"
                    type="text"
                    placeholder="Buscar por nome ou telefone..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    onFocus={handleFocus}
                    autoComplete="off"
                    disabled={isSubmitting || !!initialContact} 
                />
                {/* Dropdown List */}
                {isDropdownOpen && searchQuery && !initialContact && ( 
                    <div className="absolute z-10 w-full mt-1 bg-background border border-border rounded-md shadow-lg max-h-60 overflow-y-auto">
                        {/* ... dropdown content (loading, error, results) ... */}
                         <ul className="py-1">
                            {isSearching && ( <li className="px-3 py-2 text-sm text-muted-foreground flex items-center justify-center"><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Buscando...</li> )}
                            {searchError && !isSearching && ( <li className="px-3 py-2 text-sm text-destructive text-center">Erro: {searchError.message}</li> )}
                            {!isSearching && !searchError && (!searchResults || searchResults.length === 0) && ( <li className="px-3 py-2 text-sm text-muted-foreground text-center">Nenhum contato encontrado.</li> )}
                            {!isSearching && searchResults && searchResults.length > 0 && (
                                searchResults.map((contact) => (
                                    <li key={contact.id}>
                                        <button type="button" onClick={() => handleContactSelect(contact)} disabled={!contact.phone_number} className={cn("w-full text-left px-3 py-2 text-sm hover:bg-accent disabled:opacity-50 disabled:pointer-events-none flex flex-col")}>
                                            <span className="font-medium">{contact.name || 'Sem Nome'}</span>
                                            <span className="text-xs text-muted-foreground">{formatPhoneNumber(contact.phone_number) || 'Sem número'}</span>
                                        </button>
                                    </li>
                                ))
                            )}
                        </ul>
                    </div>
                )}
            </div>
        )}
         {/* Validation message */}
         {!selectedContact && <p className="text-xs text-destructive">Selecione ou busque um contato.</p>}
      </div>

      {/* Submit Button */}
      <Button
        type="submit"
        disabled={!selectedContact || !selectedInboxId || isSubmitting || inboxesLoading}
        className="w-full"
      >
        {/* ... submit button content ... */}
         {isSubmitting ? ( <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{loadingText}</> ) : ( submitText )}
      </Button>
    </form>
  );
}