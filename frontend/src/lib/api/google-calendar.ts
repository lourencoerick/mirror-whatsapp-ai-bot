// services/api/integrations.ts

import { FetchFunction } from "@/hooks/use-authenticated-fetch";
import { components } from "@/types/api";

// Tipos gerados pelo OpenAPI
type CalendarResponse = components["schemas"]["CalendarResponse"];

const API_V1_BASE = "/api/v1";

/**
 * Fetches the list of Google Calendars for the authenticated user.
 * This requires the user to have already connected their Google account.
 *
 * @param fetcher The authenticated fetch function from the useAuthenticatedFetch hook.
 * @returns A promise that resolves to an array of calendar objects.
 * @throws An error if the API call fails for reasons other than not being found.
 */
export const getGoogleCalendars = async (
  fetcher: FetchFunction
): Promise<CalendarResponse[]> => {
  const endpoint = `${API_V1_BASE}/integrations/google/calendars`;
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
    throw new Error(`Failed to fetch Google Calendars: ${errorDetail}`);
  }

  const data: CalendarResponse[] = await response.json();
  return data;
};
