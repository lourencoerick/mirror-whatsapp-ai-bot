// src/app/payment/cancel/page.tsx
"use client";

import { XCircleIcon } from "@heroicons/react/24/solid";
import Link from "next/link";

export default function PaymentCancelPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="bg-white p-8 md:p-12 rounded-lg shadow-xl text-center max-w-md w-full">
        <XCircleIcon className="w-16 h-16 text-red-500 mx-auto mb-6" />
        <h1 className="text-3xl font-bold text-gray-800 mb-4">
          Pagamento Cancelado
        </h1>
        <p className="text-gray-600 mb-8">
          Seu processo de pagamento foi cancelado ou não pôde ser concluído.
          Nenhuma cobrança foi feita. Você pode tentar novamente ou escolher um
          plano diferente.
        </p>
        <div className="space-y-4 md:space-y-0 md:space-x-4 flex flex-col md:flex-row justify-center">
          <Link
            href="/billing/plans" // Volta para a página de planos
            className="w-full md:w-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-md transition-colors duration-150 ease-in-out"
          >
            Ver Planos
          </Link>
          <Link
            href="/dashboard" // Ou para uma página de contato/suporte
            className="w-full md:w-auto bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold py-3 px-6 rounded-md transition-colors duration-150 ease-in-out"
          >
            Voltar ao Dashboard
          </Link>
        </div>
        <p className="text-xs text-gray-400 mt-6">
          Se você acredita que isso é um erro, por favor, contate o suporte.
        </p>
      </div>
    </div>
  );
}
