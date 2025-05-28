// src/hooks/useAuthenticatedFetch.ts
import { useAuth } from "@clerk/nextjs";
import { log } from "next-axiom"; // Supondo que 'next-axiom' é seu logger
import { useEffect, useState } from "react"; // Adicionado useEffect e useState

interface AuthenticatedFetchOptions extends RequestInit {}

export type FetchFunction = (
  url: string,
  options?: AuthenticatedFetchOptions
) => Promise<Response>;

/**
 * Custom hook that provides a fetch function pre-configured with
 * the Clerk authentication token.
 * Returns null until Clerk is loaded and the user is signed in.
 *
 * @returns {FetchFunction | null} An async function or null if auth is not ready.
 */
export function useAuthenticatedFetch(): FetchFunction | null {
  // <<< Retorna FetchFunction | null
  const { getToken, isLoaded, isSignedIn, signOut } = useAuth();

  // Estado para armazenar o fetcher memoizado uma vez que estiver pronto
  const [memoizedFetcher, setMemoizedFetcher] = useState<FetchFunction | null>(
    null
  );

  useEffect(() => {
    // Só tenta criar o fetcher se o Clerk carregou e o usuário está logado
    if (isLoaded && isSignedIn) {
      const fetchWrapper = async (
        url: string,
        options: AuthenticatedFetchOptions = {}
      ): Promise<Response> => {
        // Não precisamos mais checar isLoaded e isSignedIn aqui dentro,
        // pois o hook só retorna o fetcher quando essas condições são verdadeiras.
        // No entanto, uma verificação de token ainda é válida.

        const token = await getToken({ template: "fastapi-backend" });

        if (!token) {
          const errorMessage =
            "[useAuthenticatedFetch Internal] Auth token could not be retrieved even though signed in.";
          console.error(errorMessage);
          log.error(errorMessage);
          // Poderia tentar signOut aqui ou apenas lançar o erro
          // await signOut();
          throw new Error(
            "Authentication token issue. Please try signing out and in."
          );
        }

        const headers = new Headers(options.headers || {});
        headers.set("Authorization", `Bearer ${token}`);
        if (options.body && !headers.has("Content-Type")) {
          headers.set("Content-Type", "application/json");
        }
        if (headers.has("Content-Type") && headers.get("Content-Type") === "") {
          headers.delete("Content-Type");
        }

        const backendApiUrl =
          process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
        const fullUrl = url.startsWith("http")
          ? url
          : url.startsWith("/")
          ? `${backendApiUrl}${url}`
          : `${backendApiUrl}/${url}`;

        try {
          const requestInfo = `[useAuthenticatedFetch] Requesting: ${
            options.method || "GET"
          } ${fullUrl}`;
          console.log(requestInfo);
          // log.debug(requestInfo); // Axiom pode não ter log.debug, use info ou warn

          const response = await fetch(fullUrl, {
            ...options,
            headers: headers,
          });

          const responseInfo = `[useAuthenticatedFetch] Response Status: ${response.status} for ${fullUrl}`;
          console.log(responseInfo);
          // log.debug(responseInfo);

          if (response.status === 401) {
            const errorDetail =
              "[useAuthenticatedFetch] Received 401 Unauthorized. Signing out.";
            console.error(errorDetail);
            log.error(errorDetail);
            await signOut();
            throw new Error(
              "Unauthorized: Invalid or expired token. You have been signed out."
            );
          }
          if (response.status === 403) {
            const errorDetail =
              "[useAuthenticatedFetch] Received 403 Forbidden.";
            console.error(errorDetail);
            log.error(errorDetail);
            throw new Error("Forbidden: Access denied.");
          }
          return response;
        } catch (error) {
          const networkErrorInfo = `[useAuthenticatedFetch] Network or fetch error for ${fullUrl}:`;
          console.error(networkErrorInfo, error);
          log.error(networkErrorInfo, {
            errorMessage: (error as Error).message,
          });
          throw error;
        }
      };
      // Define o fetcher memoizado
      setMemoizedFetcher(() => fetchWrapper); // Passa a função para que o useState não a chame
    } else if (isLoaded && !isSignedIn) {
      // Clerk carregou, mas usuário não está logado, garante que o fetcher é null
      setMemoizedFetcher(null);
    }
    // Se !isLoaded, o fetcher permanece o valor anterior (null inicialmente)
    // e o useEffect será re-executado quando isLoaded mudar.
  }, [isLoaded, isSignedIn, getToken, signOut]); // Dependências do useEffect

  return memoizedFetcher; // Retorna o fetcher memoizado (ou null)
}
