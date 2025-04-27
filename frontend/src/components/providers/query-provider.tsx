// components/providers/ReactQueryProvider.tsx
"use client"; // Provider precisa ser um client component

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// import { ReactQueryDevtools } from "@tanstack/react-query-devtools"; // Opcional: Ferramentas de Dev
import React, { useState } from "react";

export default function ReactQueryProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  // Criar o cliente UMA VEZ usando useState para evitar recriação em re-renders
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Configurações padrão globais (opcional)
            staleTime: 5 * 60 * 1000, // 5 minutos - Dados são considerados frescos por 5 min
            refetchOnWindowFocus: false, // Desabilitar refetch ao focar janela (pode ser útil)
            retry: 1, // Tentar novamente 1 vez em caso de erro
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Adicionar DevTools apenas em ambiente de desenvolvimento */}
      {/* {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )} */}
    </QueryClientProvider>
  );
}
