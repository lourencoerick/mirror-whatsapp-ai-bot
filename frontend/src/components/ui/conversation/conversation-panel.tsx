import React from 'react'
import ConversationsList from './conversation-list'
import StartConversationDialog from './start-conversation-dialog'
import Search from './search';
import { Funnel, SquarePen } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ConversationPanelProps {
  socketIdentifier: string;
}

const ConversationPanel: React.FC<ConversationPanelProps> = ({ socketIdentifier }) => {
  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <div className='flex flex-col py-2 gap-2 items-center'>      
        <Search placeholder="Pesquisar..." />

      <div className="flex flex-row justify-between items-center w-full px-2">
        <span className='text-lg font-semibold'>Conversas</span>
        <div className='flex gap-1'>
          <StartConversationDialog
            trigger={
              <Button variant="outline" size="sm">
                <SquarePen size={15} className="" /> {/* Added margin for better spacing */}
              </Button>
            }
          />
          <Button variant="outline" size={"sm"}>
            <Funnel size={15} />
          </Button>
        </ div>
      </div>

      </div>



      <div className=" flex flex-col overflow-y-auto w-full max-w-xs min-w-xs">
        <ConversationsList socketIdentifier={socketIdentifier} />
      </div>
    </ div>
  )
}

export default ConversationPanel