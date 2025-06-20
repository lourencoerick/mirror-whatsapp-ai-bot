/* eslint-disable @typescript-eslint/no-unused-vars */
// services/api/integrations.ts

import { FetchFunction } from "@/hooks/use-authenticated-fetch";
import { components } from "@/types/api";

type GoogleIntegrationStatus = components["schemas"]["GoogleIntegrationStatus"];

const API_V1_BASE = "/api/v1";

/**
 * Fetches the complete status of the Google integration for the current user.
 * This includes connection status, permission scopes, and a list of calendars if applicable.
 *
 * @param fetcher The authenticated fetch function from the useAuthenticatedFetch hook.
 * @returns A promise that resolves to the GoogleIntegrationStatus object.
 * @throws An error if the API call fails.
 */
export const getGoogleIntegrationStatus = async (
  fetcher: FetchFunction
): Promise<GoogleIntegrationStatus> => {
  // O endpoint agora aponta para a nossa nova rota de status.
  const endpoint = `${API_V1_BASE}/integrations/google/status`;

  const response = await fetcher(endpoint, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) {
      /* Ignore if response has no body */
    }
    // Lançar um erro permite que o React Query gerencie o estado de erro automaticamente.
    throw new Error(
      `Failed to fetch Google integration status: ${errorDetail}`
    );
  }

  const data: GoogleIntegrationStatus = await response.json();
  return data;
};
