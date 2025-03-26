// Caixa de entrada com botões de envio, anexo e áudio
import { ChatInput } from "@/components/ui/chat/chat-input";
import { Button } from "@/components/ui/button";
import { Paperclip, Mic, CornerDownLeft } from "lucide-react";

interface ChatInputBoxProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled?: boolean;
}

export function ChatInputBox({ value, onChange, onSubmit, onKeyDown, disabled = false }: ChatInputBoxProps) {
  return (
    <form onSubmit={onSubmit} className="relative rounded-lg border bg-background focus-within:ring-1 focus-within:ring-ring">
      <ChatInput
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        placeholder="Digite sua mensagem..."
        className="rounded-lg bg-background border-0 shadow-none focus-visible:ring-0"
      />
      <div className="flex items-center p-3 pt-0">
        <Button variant="ghost" size="icon">
          <Paperclip className="size-4" />
        </Button>
        <Button variant="ghost" size="icon">
          <Mic className="size-4" />
        </Button>
        <Button type="submit" disabled={disabled} size="sm" className="ml-auto gap-1.5">
          Enviar <CornerDownLeft className="size-3.5" />
        </Button>
      </div>
    </form>
  );
}
