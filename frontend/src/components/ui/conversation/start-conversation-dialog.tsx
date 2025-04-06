
"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner"; 
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import PhoneInputForm from "@/components/ui/conversation/start-conversation-dialog-input"; 
import { startConversation } from "@/lib/actions/start-conversation"; 

/**
 * Props for the StartConversationDialog component.
 */
interface StartConversationDialogProps {
  /** The element that triggers the dialog opening. */
  trigger: React.ReactNode;
}

/**
 * A dialog component to initiate a new WhatsApp conversation.
 * Uses sonner toasts for user feedback on the start conversation action.
 * User-facing text is in Portuguese (PT-BR).
 *
 * @param {StartConversationDialogProps} props - The component props.
 * @param {React.ReactNode} props.trigger - The element that will open the dialog when clicked.
 */
export default function StartConversationDialog({ trigger }: StartConversationDialogProps) {
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const router = useRouter();

  /**
   * Handles the submission of the phone number to start a new conversation.
   * Shows loading, success, or error toasts (in PT-BR) during the process.
   * Navigates to the conversation page on success.
   *
   * @param {string} fullNumber - The complete phone number (including country code).
   * @param {string} inboxId - The ID of the inbox to use for the conversation.
   */
  const handleStartConversation = async (fullNumber: string, inboxId: string) => {
    setLoading(true);
    const toastId = toast.loading("Iniciando conversa..."); 

    try {
      const res = await startConversation({ phoneNumber: fullNumber, inboxId: inboxId });

      if (res.success && res.conversation_id) {
        toast.success("Conversa iniciada!", { 
          id: toastId,
          description: "Redirecionando...", 
        });
        setOpen(false); 
        router.push(`/dashboard/conversations/${res.conversation_id}`);
      } else {
        
        const errorMessage = res.error || "Não foi possível iniciar a conversa."; 
        toast.error("Falha ao iniciar", { 
          id: toastId,
          description: errorMessage, 
        });
        console.error("Failed to start conversation:", errorMessage);
        
      }
    } catch (err: any) {
      
      console.error("Unexpected error starting conversation:", err);
      const errorDescription = err.message || "Por favor, tente novamente mais tarde."; 
      toast.error("Ocorreu um erro inesperado", { 
        id: toastId,
        description: errorDescription, 
      });
      
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger}
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Iniciar nova conversa</DialogTitle> 
        </DialogHeader>

        <PhoneInputForm
          onPhoneSubmit={handleStartConversation}
          
          loadingText="Iniciando..."
          submitText="Iniciar"
        />
      </DialogContent>
    </Dialog>
  );
}