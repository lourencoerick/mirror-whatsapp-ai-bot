// src/app/dashboard/conversations/[conversationId]/page.tsx
"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";

// Import the reusable component
import ConversationChatView from "@/components/ui/chat/chat-view";
import { useLayoutContext } from "@/contexts/layout-context";

const ChatPage = () => {
  const { conversationId } = useParams() as { conversationId: string };
  const { setPageTitle } = useLayoutContext();

  // Set the page title
  useEffect(() => {
    setPageTitle(
      <div className="flex items-center gap-2">
        <Link
          href="/dashboard/conversations"
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          aria-label="Voltar para Conversas"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="font-semibold">Conversas</span>
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        <span className="font-semibold">Detalhes</span>
      </div>
    );
  }, [setPageTitle]);

  return (
    <main className="flex flex-col w-full h-full">
      {conversationId ? (
        <ConversationChatView
          conversationId={conversationId}
          userDirection="out"
        />
      ) : (
        <div className="p-4 text-center text-red-500">
          ID da conversa não encontrado na URL.
        </div>
      )}
    </main>
  );
};

export default ChatPage;
