/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';

import React, { useMemo } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import ConversationsList from './conversation-list';
import Search from './search';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ConversationStatusEnum } from '@/types/conversation'; // Adjust path if needed
import { ConversationFilters } from '@/hooks/use-conversations'; // Adjust path if needed

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
  // Defaults to 'human' if param is null, empty, or invalid
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
        // Fallback (shouldn't happen with getValidFilterPreset)
        return {
          status: [ConversationStatusEnum.PENDING, ConversationStatusEnum.HUMAN_ACTIVE],
          has_unread: null,
          query: baseQuery,
        };
    }
  }, [query, activeFilter]);

  const handleFilterChange = (newFilter: FilterPreset) => {
    const current = new URLSearchParams(Array.from(searchParams.entries()));

    // Default state ('human') removes the param for cleaner URL
    if (newFilter === 'human') {
      current.delete('filter');
    } else {
      // Explicitly set for 'unread', 'closed', and 'all'
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
      <div className="py-2 px-2 flex space-x-0.5 w-xs">
        <Button
          variant={activeFilter === 'human' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('human')}
          className={cn("flex-1", activeFilter === 'human' && "font-semibold")}
        >
          Atendimento
        </Button>
        <Button
          variant={activeFilter === 'unread' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('unread')}
          className={cn("flex-1", activeFilter === 'unread' && "font-semibold")}
        >
          Não Lidas
        </Button>
        <Button
          variant={activeFilter === 'closed' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('closed')}
          className={cn("flex-1", activeFilter === 'closed' && "font-semibold")}
        >
          Fechadas
        </Button>

        {/* 'Todas' button */}
        <Button
          variant={activeFilter === 'all' ? 'secondary' : 'ghost'}
          size="xs"
          onClick={() => handleFilterChange('all')}
          className={cn("flex-1", activeFilter === 'all' && "font-semibold")}
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