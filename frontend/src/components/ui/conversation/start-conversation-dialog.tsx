"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { SquarePen } from "lucide-react";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import PhoneInputForm from "@/components/ui/phone-input";
import api from "@/lib/api";

interface Props {
  inboxId: string;
}

export default function StartConversationDialog({ inboxId }: Props) {
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false)
  const router = useRouter();

  const handleStartConversation = async (fullNumber: string) => {
    setLoading(true);
    try {
      const res = await api.post(`/inboxes/${inboxId}/conversations`, {
        phone_number: fullNumber,
      });
      const { conversation_id } = res.data;
      setOpen(false);
      router.push(`/dashboard/inboxes/${inboxId}/conversations/${conversation_id}`);
    } catch (err) {
      console.error("Failed to start conversation", err);
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

        <PhoneInputForm onPhoneSubmit={handleStartConversation} loadingText="Iniciando..." submitText="Iniciar"/>
      </DialogContent>
    </Dialog>
  );
}
