// src/app/payment/success/page.tsx
"use client";

import { useSubscription } from "@/contexts/subscription-context";
import { CheckCircleIcon } from "@heroicons/react/24/solid"; // Ícone opcional
import Link from "next/link";
import { useSearchParams } from "next/navigation"; // Para ler query params
import { Suspense, useEffect } from "react";

// Componente interno para usar useSearchParams, pois ele precisa estar dentro de <Suspense>
function SuccessContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const {
    invalidateSubscriptionQuery,
    refetchSubscription,
    isLoadingSubscription,
    subscription,
  } = useSubscription();

  useEffect(() => {
    if (sessionId) {
      console.log(
        "Pagamento bem-sucedido! Stripe Checkout Session ID:",
        sessionId
      );
      invalidateSubscriptionQuery();
      // Aqui você poderia, opcionalmente, fazer uma chamada à API para:
      // 1. Verificar o status da sessão de checkout (stripe.checkout.sessions.retrieve(sessionId) no backend).
      // 2. Invalidar queries do React Query/SWR para forçar a atualização do status da assinatura.
      // Por exemplo, se você usa TanStack Query: queryClient.invalidateQueries(['mySubscription']);
      // Por enquanto, vamos assumir que o webhook já atualizou o backend.
    }
  }, [sessionId, invalidateSubscriptionQuery, refetchSubscription]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="bg-white p-8 md:p-12 rounded-lg shadow-xl text-center max-w-md w-full">
        <CheckCircleIcon className="w-16 h-16 text-green-500 mx-auto mb-6" />
        <h1 className="text-3xl font-bold text-gray-800 mb-4">
          Pagamento Bem-Sucedido!
        </h1>
        <p className="text-gray-600 mb-8">
          Obrigado por sua assinatura! Seu plano foi ativado. Você pode
          gerenciar sua assinatura e acessar todos os recursos agora.
        </p>
        <div className="space-y-4 md:space-y-0 md:space-x-4 flex flex-col md:flex-row justify-center">
          <Link
            href="/dashboard"
            className="w-full md:w-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-md transition-colors duration-150 ease-in-out"
          >
            Ir para o Dashboard
          </Link>
          <Link
            href="/dashboard/account/subscription" // Link para a futura página de gerenciamento de assinatura
            className="w-full md:w-auto bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold py-3 px-6 rounded-md transition-colors duration-150 ease-in-out"
          >
            Ver Minha Assinatura
          </Link>
        </div>
        {/* {sessionId && (
          <p className="text-xs text-gray-400 mt-6">
            ID da Sessão: {sessionId}
          </p>
        )} */}
      </div>
    </div>
  );
}

export default function PaymentSuccessPage() {
  // useSearchParams precisa ser usado dentro de um componente envolvido por <Suspense>
  // Se esta página for renderizada no servidor inicialmente, o Suspense é importante.
  return (
    <Suspense
      fallback={
        <div className="flex justify-center items-center min-h-screen">
          Carregando...
        </div>
      }
    >
      <SuccessContent />
    </Suspense>
  );
}
