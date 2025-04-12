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

type FilterPreset = 'human' | 'unread' | 'closed';

// Helper to validate filter preset from URL
function getValidFilterPreset(filterParam: string | null): FilterPreset {
  if (filterParam === 'unread' || filterParam === 'closed') {
    return filterParam;
  }
  return 'human';
}

const ConversationPanel: React.FC<ConversationPanelProps> = ({ socketIdentifier }) => {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.get('query');

  // Read active filter from URL
  const activeFilter = getValidFilterPreset(searchParams.get('filter'));

  // Construct filters object based on activeFilter from URL
  const filters = useMemo<ConversationFilters>(() => {
    const baseFilters: ConversationFilters = { query: query || null };
    switch (activeFilter) {
      case 'human':
        return {
          status: [ConversationStatusEnum.PENDING, ConversationStatusEnum.HUMAN_ACTIVE],
          has_unread: null,
          query: baseFilters.query,
        };
      case 'unread':
        return {
          status: [ConversationStatusEnum.PENDING, ConversationStatusEnum.HUMAN_ACTIVE],
          has_unread: true,
          query: baseFilters.query,
        };
      case 'closed':
        return {
          status: [ConversationStatusEnum.CLOSED],
          has_unread: null,
          query: baseFilters.query,
        };
      default:
        return baseFilters;
    }
  }, [query, activeFilter]);

  // Handler to change filter via URL
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
      <div className="flex flex-col py-4 px-2">
        <Search placeholder="Pesquisar..." />
      </div>

      {/* Filter Buttons */}
      <div className="pb-1 px-2 flex space-x-2">
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
