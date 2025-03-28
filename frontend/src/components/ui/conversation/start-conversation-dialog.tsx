"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SquarePen } from "lucide-react";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import PhoneInputForm from "@/components/ui/conversation/start-conversation-dialog-input";
import { startConversation } from "@/lib/actions/start-conversation";



export default function StartConversationDialog() {
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const router = useRouter(); 

  const handleStartConversation = async (fullNumber: string, inboxId: string) => {
    setLoading(true);
    try {
      const res = await startConversation({ phoneNumber: fullNumber, inboxId: inboxId });

      if (res.success && res.conversation_id) {
        setOpen(false);
        router.push(`/dashboard/conversations/${res.conversation_id}`);
      } else {
        console.error("Failed to start conversation", res.error);
      }
    } catch (err) {
      console.error("Unexpected error", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
          <SquarePen size={15} />
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Inicie uma nova conversa</DialogTitle>
        </DialogHeader>

        <PhoneInputForm
          onPhoneSubmit={(fullNumber, inboxId) => handleStartConversation(fullNumber, inboxId)}
          loadingText="Iniciando..."
          submitText="Iniciar"
        />
      </DialogContent>
    </Dialog>
  );
}
