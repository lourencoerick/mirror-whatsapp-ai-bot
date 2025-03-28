import React from 'react'
import { useParams } from 'next/navigation';
import ConversationsList from './conversation-list'
import StartConversationDialog from './start-conversation-dialog'
import Search from './search';
import { Funnel } from 'lucide-react';
import { Button } from '@/components/ui/button';


const ConversationPanel = () => {
  const { conversationId } = useParams() as { conversationId: string };
  return (
    <div className="h-screen flex flex-col bg-slate-50 pt-4 gap-2 items-center">

      <Search placeholder="Pesquisar..." />

      <div className="flex flex-row justify-between items-center w-full px-2">
        <span className='text-lg font-semibold'>Conversas</span>
        <div className='flex gap-1'>
          <StartConversationDialog />
          <Button variant="outline" size={"sm"}>
            <Funnel size={15} />
          </Button>
        </ div>
      </div>


      <div className=" flex flex-col overflow-y-auto w-full max-w-sm">
        <ConversationsList />
      </div>
    </ div>
  )
}

export default ConversationPanel