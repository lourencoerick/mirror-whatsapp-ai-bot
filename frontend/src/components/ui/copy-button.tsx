// Exemplo em "@/components/ui/copy-button.tsx"
import { Button } from "@/components/ui/button";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

interface CopyButtonProps {
  valueToCopy: string;
}
export const CopyButton: React.FC<CopyButtonProps> = ({ valueToCopy }) => {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard
      .writeText(valueToCopy)
      .then(() => {
        setCopied(true);
        toast.success("Copiado para a área de transferência!");
        setTimeout(() => setCopied(false), 2000);
      })
      .catch((err) => {
        toast.error("Falha ao copiar.");
        console.error("Failed to copy: ", err);
      });
  };
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={handleCopy}
      aria-label="Copiar"
    >
      {copied ? (
        <Check className="h-4 w-4 text-green-500" />
      ) : (
        <Copy className="h-4 w-4" />
      )}
    </Button>
  );
};
