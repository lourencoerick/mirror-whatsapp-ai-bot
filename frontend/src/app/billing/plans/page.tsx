"use client";

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { createCheckoutSession } from "@/lib/api/billing";
import { components } from "@/types/api";
import { useUser } from "@clerk/nextjs";
import { useState } from "react";

// Definição do tipo para um plano (pode ser expandido)
interface Plan {
  id: string; // Identificador interno do plano (ex: 'basic', 'pro')
  name: string;
  price: string;
  currency: string;
  stripePriceId: string; // O ID do Price do Stripe (price_xxxx)
  features: string[];
  description?: string;
}

// Dados dos planos (hardcoded por enquanto)
const plansData: Plan[] = [
  {
    id: "basic",
    name: "Plano Básico",
    price: "9,99",
    currency: "R$",
    stripePriceId: "price_1RRh5wQH91QtB7wz8hMFWuX9",
    features: ["Recurso A", "Recurso B", "Suporte por Email"],
    description: "Ideal para começar.",
  },
  {
    id: "pro",
    name: "Plano Pro",
    price: "29,99",
    currency: "R$",
    stripePriceId: "price_1RSJjFQH91QtB7wz04dgSkLT",
    features: [
      "Tudo do Básico",
      "Recurso C Avançado",
      "Recurso D",
      "Suporte Prioritário",
    ],
    description: "Para usuários que precisam de mais poder.",
  },

  {
    id: "enterprise",
    name: "Plano Enterprise",
    price: "100,99",
    currency: "R$",
    stripePriceId: "price_1RSjfFQH91QtB7wzY7C2GqrS",
    features: ["Tudo do Pro", "Suporte 1:1"],
    description: "Para usuários que precisam de mais e mais poder.",
  },
  // Adicione mais planos conforme necessário
];

type CreateCheckoutSessionResponse =
  components["schemas"]["CreateCheckoutSessionResponse"];

export default function BillingPlansPage() {
  const { user } = useUser();
  const fetcher = useAuthenticatedFetch();
  const [isLoading, setIsLoading] = useState<Record<string, boolean>>({}); // Para feedback de carregamento por plano
  const [error, setError] = useState<string | null>(null);

  const handleSubscribe = async (plan: Plan) => {
    if (!user || !fetcher) {
      setError("Usuário não autenticado ou fetcher não disponível.");
      return;
    }

    setIsLoading((prev) => ({ ...prev, [plan.id]: true }));
    setError(null);

    try {
      console.log(
        `Iniciando assinatura para o plano: ${plan.name}, Price ID: ${plan.stripePriceId}`
      );
      const payload = { price_id: plan.stripePriceId };
      const response: CreateCheckoutSessionResponse =
        await createCheckoutSession(fetcher, payload);

      if (response.checkout_url) {
        console.log(
          "Redirecionando para Stripe Checkout URL:",
          response.checkout_url
        );
        // Redireciona o usuário para a URL de checkout do Stripe
        window.location.href = response.checkout_url;
      } else {
        console.error("Resposta da API não continha checkout_url:", response);
        setError(
          "Não foi possível iniciar a sessão de pagamento. Tente novamente."
        );
      }
    } catch (err) {
      console.error("Erro ao criar sessão de checkout:", err);
      const errorMessage =
        err instanceof Error ? err.message : "Ocorreu um erro desconhecido.";
      setError(`Falha ao iniciar pagamento: ${errorMessage}`);
    } finally {
      setIsLoading((prev) => ({ ...prev, [plan.id]: false }));
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8 text-center">Nossos Planos</h1>

      {error && (
        <div className="mb-4 p-4 text-red-700 bg-red-100 border border-red-400 rounded">
          <p>
            <strong>Erro:</strong> {error}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {plansData.map((plan) => (
          <div
            key={plan.id}
            className="border rounded-lg p-6 shadow-lg flex flex-col"
          >
            <h2 className="text-2xl font-semibold mb-2">{plan.name}</h2>
            {plan.description && (
              <p className="text-gray-600 mb-4">{plan.description}</p>
            )}
            <p className="text-4xl font-bold mb-4">
              {plan.currency} {plan.price}
              <span className="text-lg font-normal text-gray-500">/mês</span>
            </p>
            <ul className="mb-6 space-y-2 text-gray-700 flex-grow">
              {plan.features.map((feature, index) => (
                <li key={index} className="flex items-center">
                  <svg
                    className="w-5 h-5 text-green-500 mr-2"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    ></path>
                  </svg>
                  {feature}
                </li>
              ))}
            </ul>
            <button
              onClick={() => handleSubscribe(plan)}
              disabled={isLoading[plan.id]}
              className={`w-full py-3 px-4 rounded-md font-semibold text-white transition-colors
                ${
                  isLoading[plan.id]
                    ? "bg-gray-400 cursor-not-allowed"
                    : "bg-blue-600 hover:bg-blue-700"
                }`}
            >
              {isLoading[plan.id] ? "Processando..." : "Assinar Agora"}
            </button>
          </div>
        ))}
      </div>
      <p className="mt-8 text-center text-sm text-gray-500">
        Os pagamentos são processados de forma segura pelo Stripe.
      </p>
    </div>
  );
}
