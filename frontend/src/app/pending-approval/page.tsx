// app/pending-approval/page.tsx
"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { UserButton } from "@clerk/nextjs";
import { Clock, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";

/**
 * PendingApprovalPage displays a confirmation message
 * when a user’s beta access is being reviewed.
 */
export default function PendingApprovalPage() {
  const router = useRouter(); // Hook para navegação

  const handleRefreshOrHome = () => {
    router.push("/");
  };

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
            Devido ao grande volume de inscrições para o nosso beta,{" "}
            <strong>avaliamos cada candidatura com o máximo de atenção</strong>.
          </p>
          <p className="text-sm text-muted-foreground">
            Se você for selecionado, em breve receberá{" "}
            <strong>instruções para nos contar mais sobre sua empresa</strong> e
            descobrir como, juntos, podemos{" "}
            <strong>
              transformar seu WhatsApp em uma verdadeira máquina de vendas
            </strong>
            !
          </p>
        </CardContent>
        <CardFooter className="flex flex-col items-center justify-center pt-2 pb-6">
          {" "}
          {/* Adicionado CardFooter */}
          <Button onClick={handleRefreshOrHome} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Tentar Novamente
          </Button>
        </CardFooter>
      </Card>
    </main>
  );
}
