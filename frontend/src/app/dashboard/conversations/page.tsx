"use client";

import { Button } from "@/components/ui/button";
import { PlusCircle } from "lucide-react";
import { useLayoutContext } from '@/contexts/layout-context';
import StartConversationDialog from '@/components/ui/conversation/start-conversation-dialog'

const ConversationsPage = () => {

  const { setPageTitle } = useLayoutContext();
  setPageTitle("Conversas");

  return (
    <div className="flex h-full">
      <div className="w-full flex flex-col items-center justify-center p-4">
        <div className="text-center">
          <h2 className="text-2xl font-semibold mb-4">Bem-vindo(a) a suas conversas!</h2>
          <p className="text-gray-600 mb-4">
            Selecione uma conversa para ver as mensagens ou comece uma nova.
          </p>

          <StartConversationDialog
            trigger={
              <Button variant="outline">
                <PlusCircle className="mr-2 h-4 w-4" />
                Iniciar uma conversa
              </Button>
            }
          />

        </div>
      </div>
    </div>
  );
};

export default ConversationsPage;