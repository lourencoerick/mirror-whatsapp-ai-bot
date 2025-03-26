import React from 'react'
import ConversationsList from './conversation-list'
import Search from './search';
import { SquarePen, Funnel } from 'lucide-react';
import { Button } from '@/components/ui/button';
type Props = {}

const ConversationPanel = (props: Props) => {
  return (
    <div className="h-screen flex flex-col bg-slate-50 pt-4 gap-2 items-center">

      <Search placeholder="Pesquisar..." />

      <div className="flex flex-row justify-between items-center w-full px-2">
        <span className='text-lg font-semibold'>Conversas</span>
        <div className='flex gap-1'>
          <Button variant="outline" size={"sm"}>
            <SquarePen size={15} />
          </Button>
          <Button variant="outline" size={"sm"}>
            <Funnel size={15} />
          </Button>
        </ div>
      </div>


      <div className=" flex flex-col overflow-y-auto w-full">
        <ConversationsList />
      </div>
    </ div>
  )
}

export default ConversationPanel