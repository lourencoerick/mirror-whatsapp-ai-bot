"use client";

import React, { useState, useEffect } from "react"; 
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { StartConversationForm } from "@/components/ui/conversation/start-conversation-form"; 
import { startConversation } from "@/lib/actions/start-conversation";
import { Contact } from "@/types/contact"; 

interface StartConversationDialogProps {
  /** The element that triggers the dialog opening. */
  trigger?: React.ReactNode; 
  /** Optional: Pre-selects a contact */
  initialContact?: Contact | null;
  /** Controls the open state if used as a controlled component */
  open?: boolean;
  /** Callback when the open state changes */
  onOpenChange?: (open: boolean) => void;
}

export default function StartConversationDialog({
    trigger,
    initialContact = null,
    open: controlledOpen,
    onOpenChange: controlledOnOpenChange,
}: StartConversationDialogProps) {
  // Use internal state if not controlled externally
  const [internalOpen, setInternalOpen] = useState(false);
  const isControlled = controlledOpen !== undefined && controlledOnOpenChange !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;
  const setOpen = isControlled ? controlledOnOpenChange : setInternalOpen;

  const router = useRouter();

  // Reset internal state when dialog closes (if uncontrolled)
  useEffect(() => {
      if (!isControlled && !open) {
      }
  }, [open, isControlled]);


  const handleStartConversationSubmit = async (phoneNumber: string, inboxId: string) => {
    const toastId = toast.loading("Iniciando conversa...");
    try {
      const res = await startConversation({ phoneNumber: phoneNumber, inboxId: inboxId });
      if (res.success && res.conversation_id) {
        toast.success("Conversa iniciada!", { id: toastId, description: "Redirecionando..." });
        setOpen(false); // Close the dialog
        router.push(`/dashboard/conversations/${res.conversation_id}`);
      } else {
        toast.error("Falha ao iniciar", { id: toastId, description: res.error || "Não foi possível iniciar a conversa." });
      }
    } catch (err: unknown) {
      const errorDescription =
        err instanceof Error ? err.message : "Por favor, tente novamente.";
      toast.error("Ocorreu um erro inesperado", { id: toastId, description: errorDescription });
    }
    
  };

  const dialogTitle = initialContact ? `Enviar para ${initialContact.name || initialContact.phone_number}` : "Iniciar Nova Conversa";
  const dialogDescription = initialContact ? `Selecione a caixa de entrada para enviar a mensagem.` : `Selecione uma caixa de entrada e busque/selecione o contato desejado.`;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {/* Only render trigger if provided and not controlled */}
      {!isControlled && trigger && (
          <DialogTrigger asChild>
            {trigger}
          </DialogTrigger>
      )}

      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>{dialogDescription}</DialogDescription>
        </DialogHeader>
        <div className="py-4">
          {/* Pass initialContact to the form */}
          <StartConversationForm
            initialContact={initialContact} // Pass down the prop
            onStartConversation={handleStartConversationSubmit}
            submitText="Iniciar Conversa"
            loadingText="Iniciando..."
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}