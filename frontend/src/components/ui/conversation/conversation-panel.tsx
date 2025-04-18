'use client';

import React, { useMemo } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import ConversationsList from './conversation-list';
import Search from './search';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ConversationStatusEnum } from '@/types/conversation'; 
import { ConversationFilters } from '@/hooks/use-conversations';

interface ConversationPanelProps {
  socketIdentifier: string;
}

type FilterPreset = 'human' | 'unread' | 'closed' | 'all';

/**
 * Helper to validate filter preset from URL.
 * @param {string | null} filterParam - The 'filter' query parameter.
 * @returns {FilterPreset} The validated filter preset.
 */
function getValidFilterPreset(filterParam: string | null): FilterPreset {
  if (filterParam === 'all' || filterParam === 'unread' || filterParam === 'closed') {
    return filterParam;
  }
  return 'human';
}

/**
 * Panel component displaying conversation search, filters, and list.
 * @param {ConversationPanelProps} props - Component props.
 */
const ConversationPanel: React.FC<ConversationPanelProps> = ({ socketIdentifier }) => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.get('query');
  const activeFilter = getValidFilterPreset(searchParams.get('filter'));

  const filters = useMemo<ConversationFilters>(() => {
    const baseQuery = query || null;
    switch (activeFilter) {
      case 'human':
        return {
          status: [ConversationStatusEnum.PENDING, ConversationStatusEnum.HUMAN_ACTIVE],
          has_unread: null,
          query: baseQuery,
        };
      case 'unread':
        return {
          status: [ConversationStatusEnum.PENDING, ConversationStatusEnum.HUMAN_ACTIVE],
          has_unread: true,
          query: baseQuery,
        };
      case 'closed':
        return {
          status: [ConversationStatusEnum.CLOSED],
          has_unread: null,
          query: baseQuery,
        };
      case 'all':
        return {
          status: null, // No status filter
          has_unread: null,
          query: baseQuery,
        };
      default:
        return {
          status: [ConversationStatusEnum.PENDING, ConversationStatusEnum.HUMAN_ACTIVE],
          has_unread: null,
          query: baseQuery,
        };
    }
  }, [query, activeFilter]);

  const handleFilterChange = (newFilter: FilterPreset) => {
    const current = new URLSearchParams(Array.from(searchParams.entries()));
    if (newFilter === 'human') {
      current.delete('filter');
    } else {
      current.set('filter', newFilter);
    }
    const search = current.toString();
    const queryStr = search ? `?${search}` : "";
    router.replace(`${pathname}${queryStr}`);
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50 border-r">
      {/* Top Section */}
      <div className="flex flex-col py-2 px-2">
        <Search placeholder="Pesquisar..." />
      </div>

      {/* Filter Buttons */}
      <div className="py-2 px-2 flex space-x-0.5 w-full"> {/* Ajustado para w-full */}
        <Button
          variant={activeFilter === 'human' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('human')}
          className={cn(
            "flex-1 rounded-none", 
            activeFilter === 'human'
              ? "font-semibold border-b-2 border-primary" 
              : "border-b-2 border-transparent" 
          )}
        >
          Atendimento
        </Button>
        <Button
          variant={activeFilter === 'unread' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('unread')}
          className={cn(
            "flex-1 rounded-none",
            activeFilter === 'unread'
              ? "font-semibold border-b-2 border-primary"
              : "border-b-2 border-transparent"
          )}
        >
          Não Lidas
        </Button>
         <Button
          variant={activeFilter === 'closed' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('closed')}
          className={cn(
            "flex-1 rounded-none",
            activeFilter === 'closed'
              ? "font-semibold border-b-2 border-primary"
              : "border-b-2 border-transparent"
          )}
        >
          Fechadas
        </Button>
        <Button
          variant={activeFilter === 'all' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('all')}
          className={cn(
            "flex-1 rounded-none",
            activeFilter === 'all'
              ? "font-semibold border-b-2 border-primary"
              : "border-b-2 border-transparent"
          )}
        >
          Todas
        </Button>
      </div>

      {/* Conversation List Section */}
      <div className="flex-grow overflow-y-auto w-full">
        <ConversationsList
          socketIdentifier={socketIdentifier}
          filters={filters}
        />
      </div>
    </div>
  );
}

export default ConversationPanel;