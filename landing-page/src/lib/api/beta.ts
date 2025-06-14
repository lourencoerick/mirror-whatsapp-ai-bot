/* eslint-disable @typescript-eslint/no-unused-vars */
/**
 * @file API service for handling beta sign-ups.
 */

/**
 * The expected data structure for a beta sign-up submission.
 */
interface BetaSignupData {
  name: string;
  email: string;
}

/**
 * Submits beta user data to the backend API.
 * 
 * This function encapsulates the fetch logic, including headers,
 * body serialization, and error handling.
 *
 * @param {BetaSignupData} data The user's name and email.
 * @returns {Promise<any>} The JSON response from the server on success.
 * @throws {Error} Throws an error if the network request fails or the server returns an error status.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function submitBetaUser(data: BetaSignupData): Promise<any> {
  const response = await fetch("/api/sheet", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let errorMsg = "Ocorreu um erro ao registrar seu interesse.";
    try {
      // Try to parse a more specific error message from the backend.
      const errorResult = await response.json();
      errorMsg = errorResult.detail || errorMsg;
    } catch (e) {
      // Ignore if response body isn't JSON.
    }
    throw new Error(errorMsg);
  }

  return response.json();
}