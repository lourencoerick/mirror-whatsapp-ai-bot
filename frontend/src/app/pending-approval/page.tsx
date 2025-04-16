// app/pending-approval/page.tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Clock } from "lucide-react";
import { Metadata } from "next";
import { UserButton } from "@clerk/nextjs";

export const metadata: Metadata = {
  title: "Aplicação Recebida",
  description: "Sua inscrição para participar do beta está sendo analisada.",
};

/**
 * PendingApprovalPage displays a confirmation message
 * when a user’s beta access is being reviewed.
 */
export default function PendingApprovalPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <div className="absolute top-4 right-4">
        <UserButton />
      </div>

      <Card className="w-full max-w-md text-center">
        <CardHeader className="space-y-2 pt-6">
          <div
            role="img"
            aria-label="Relógio indicando status pendente"
            className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted"
          >
            <Clock className="h-6 w-6 text-muted-foreground" />
          </div>
          <CardTitle className="text-2xl font-semibold">
            Inscrição Recebida!
          </CardTitle>
          <CardDescription>
            Obrigado pelo seu interesse em nosso programa beta.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4 pb-6">
          <p className="text-sm text-muted-foreground">
            Devido ao grande volume de inscrições para o nosso beta, <strong>avaliamos cada candidatura com o máximo de atenção</strong>.
          </p>
          <p className="text-sm text-muted-foreground">
            Se você for selecionado, em breve receberá <strong>instruções para nos contar mais sobre sua empresa</strong> e descobrir como, juntos, podemos <strong>transformar seu WhatsApp em uma verdadeira máquina de vendas</strong>!
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
