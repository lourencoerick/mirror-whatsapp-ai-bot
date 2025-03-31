import { log } from 'next-axiom';

/**
 * Fetches the Clerk authentication token from the dedicated API route client-side.
 * This function calls the `/api/token` endpoint within the Next.js app.
 *
 * @returns {Promise<string | null>} The JWT token or null if fetching fails or user is not authenticated.
 */
export async function getClientAuthToken(): Promise<string | null> {
  try {
    // Fetch from our own API route. Relative URL works client-side.
    const response = await fetch('/api/token'); // Calls the Next.js API route

    if (!response.ok) {
      const errorText = await response.text();
      const errorMessage = `[getClientAuthToken] Failed to fetch auth token: ${response.status} ${response.statusText}. Body: ${errorText}`;
      console.error(errorMessage);
      log.error(errorMessage);

      // Handle specific errors, e.g., 401 might mean session expired or user signed out
      if (response.status === 401) {
          // Optional: Trigger sign-out or redirect here if needed globally
          console.warn("[getClientAuthToken] Received 401, user might be signed out.");
          window.location.href = '/sign-in?session_expired=true';
      }
      return null; // Return null on failure
    }

    const data = await response.json();
    if (!data.token) {
        const warningMessage = "[getClientAuthToken] Token endpoint responded OK but token was missing in response.";
        console.warn(warningMessage);
        log.warn(warningMessage);
        return null;
    }
    return data.token;

  } catch (error) {
    const errorMessage = "[getClientAuthToken] Network or other error fetching auth token:";
    console.error(errorMessage, error);
    log.error(errorMessage, { error });
    return null; // Return null on error
  }
}