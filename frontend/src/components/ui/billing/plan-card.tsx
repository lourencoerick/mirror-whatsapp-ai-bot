// src/components/billing/PlanCard.tsx
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
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch"; // Para o fetcher
import { createCheckoutSession } from "@/lib/api/billing"; // API call
import { components } from "@/types/api";
import { useUser } from "@clerk/nextjs"; // Para verificar autenticação
import { CheckIcon, Loader2 } from "lucide-react";
import { useState } from "react"; // Adicionado useState
import { toast } from "sonner"; // Para feedback

export interface Plan {
  id: string;
  tier: string;
  name: string;
  price: string;
  currency: string;
  stripeProductId: string;
  stripePriceId: string;
  features: string[];
  description?: string;
  isBeta?: boolean;
  buttonText?: string;
  buttonVariant?:
    | "default"
    | "secondary"
    | "destructive"
    | "outline"
    | "ghost"
    | "link";
  highlight?: boolean;
}

type CreateCheckoutSessionResponse =
  components["schemas"]["CreateCheckoutSessionResponse"];

interface PlanCardProps {
  plan: Plan;
  // onSubscribe é removido, a lógica de subscribe agora é interna
  // isLoading e isDisabled podem ser gerenciados internamente ou passados se houver lógica externa
  isDisabledByParent?: boolean; // Se a página pai precisa desabilitar por outras razões (ex: beta não aprovado)
  onSubscriptionError?: (errorMsg: string) => void; // Callback para erros que a página pai pode querer tratar
}

export function PlanCard({
  plan,
  isDisabledByParent = false,
  onSubscriptionError,
}: PlanCardProps) {
  const { user, isSignedIn } = useUser();
  const fetcher = useAuthenticatedFetch();
  const [isLoading, setIsLoading] = useState(false); // Estado de carregamento interno

  const handleSubscribeInternal = async () => {
    if (!isSignedIn || !fetcher) {
      const errorMsg = "Você precisa estar autenticado para assinar um plano.";
      toast.error("Autenticação Necessária", { description: errorMsg });
      if (onSubscriptionError) onSubscriptionError(errorMsg);
      return;
    }

    setIsLoading(true);
    if (onSubscriptionError) onSubscriptionError(""); // Limpar erro anterior na página pai

    try {
      console.log(
        `[PlanCard] Iniciando assinatura para: ${plan.name}, Price ID: ${plan.stripePriceId}`
      );
      const payload = { price_id: plan.stripePriceId };
      const response: CreateCheckoutSessionResponse =
        await createCheckoutSession(fetcher, payload);

      if (response.checkout_url) {
        console.log(
          "[PlanCard] Redirecionando para Stripe Checkout URL:",
          response.checkout_url
        );
        window.location.href = response.checkout_url;
      } else {
        const errorMsg =
          "Não foi possível iniciar a sessão de pagamento. Resposta da API incompleta.";
        console.error("[PlanCard]", errorMsg, response);
        toast.error("Erro no Checkout", { description: errorMsg });
        if (onSubscriptionError) onSubscriptionError(errorMsg);
      }
    } catch (err) {
      console.error("[PlanCard] Erro ao criar sessão de checkout:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Ocorreu um erro desconhecido.";
      toast.error("Erro ao Assinar", { description: errorMessage });
      if (onSubscriptionError)
        onSubscriptionError(`Falha ao iniciar pagamento: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  const effectiveButtonText =
    plan.buttonText || (plan.isBeta ? "Ativar Acesso Beta" : "Assinar Agora");
  const isButtonDisabled = isLoading || isDisabledByParent;

  return (
    <Card
      className={`flex flex-col h-full shadow-lg hover:shadow-xl transition-shadow duration-300
                  ${
                    plan.highlight
                      ? "border-2 border-blue-500 ring-4 ring-blue-500/30"
                      : "border"
                  }
                  ${plan.isBeta && !plan.highlight ? "border-blue-400" : ""}`}
    >
      <CardHeader className="pb-4">
        <CardTitle
          className={`text-2xl font-semibold ${
            plan.isBeta ? "text-blue-600" : ""
          }`}
        >
          {plan.name}
        </CardTitle>
        {plan.description && (
          <CardDescription className="text-sm text-gray-500 h-10">
            {plan.description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex-grow pt-2 pb-6">
        <div className="mb-6 text-center">
          <span
            className={`text-5xl font-extrabold ${
              plan.isBeta ? "text-blue-600" : "text-gray-900"
            }`}
          >
            {plan.price}
          </span>
          {plan.price.toLowerCase() !== "grátis" &&
            plan.price.toLowerCase() !== "gratuito" && (
              <span className="text-xl font-medium text-gray-500">
                {plan.currency === "R$" ? "/mês" : ` ${plan.currency}/mês`}
              </span>
            )}
        </div>
        <ul className="space-y-3 text-gray-600">
          {plan.features.map((feature, index) => (
            <li key={index} className="flex items-start">
              <CheckIcon className="w-5 h-5 text-green-500 mr-2 mt-0.5 flex-shrink-0" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter>
        <Button
          onClick={handleSubscribeInternal} // Chama a função interna
          disabled={isButtonDisabled}
          className={`w-full py-3 text-base font-semibold
            ${
              isButtonDisabled
                ? "bg-gray-300 cursor-not-allowed"
                : plan.buttonVariant === "secondary"
                ? "bg-gray-200 text-gray-800 hover:bg-gray-300"
                : plan.isBeta
                ? "bg-blue-600 hover:bg-blue-700"
                : "bg-slate-800 hover:bg-slate-900"
            }
            ${plan.buttonVariant && !isButtonDisabled ? "" : "text-white"}
          `}
          variant={
            plan.buttonVariant && !isButtonDisabled
              ? plan.buttonVariant
              : "default"
          }
        >
          {isLoading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : null}
          {isLoading ? "Processando..." : effectiveButtonText}
        </Button>
      </CardFooter>
    </Card>
  );
}
