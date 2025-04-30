// src/lib/api/simulation.ts

import { FetchFunction } from "@/hooks/use-authenticated-fetch";
import { components } from "@/types/api";

// Define the specific response schema type we expect
type SimulationDetailsResponse =
  components["schemas"]["SimulationDetailsResponse"];

type SimulationMessageEnqueueResponse =
  components["schemas"]["SimulationMessageEnqueueResponse"];

type SimulationMessageCreate = components["schemas"]["SimulationMessageCreate"];

// Define the API prefix for simulation endpoints
const SIMULATION_API_PREFIX = "/api/v1/simulation";

/**
 * Fetches the primary simulation entity IDs (inbox, contact, conversation)
 * for the currently authenticated user from the backend API.
 *
 * @param {FetchFunction} fetcher - The authenticated fetch function provided by a hook like useAuthenticatedFetch.
 * @returns {Promise<SimulationDetailsResponse>} A promise that resolves with the simulation details containing the necessary UUIDs.
 * @throws {Error} Throws an error if the API call fails (e.g., network error, non-OK status code, authentication issue).
 *                 The error message attempts to include details from the API response if available.
 */
export const getSimulationDetails = async (
  fetcher: FetchFunction
): Promise<SimulationDetailsResponse> => {
  // Construct the full endpoint URL
  const endpoint = `${SIMULATION_API_PREFIX}/details`;
  console.log(`[API Client] Fetching simulation details from: ${endpoint}`);

  try {
    const response = await fetcher(endpoint, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    // Check if the request was successful (status code 2xx)
    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        console.warn(
          "[API Client] Could not parse error response body as JSON.",
          e
        );
      }
      // Throw an error that can be caught by react-query or other error handlers
      throw new Error(`Failed to fetch simulation details: ${errorDetail}`);
    }

    // Parse the successful JSON response into the expected type
    const data: SimulationDetailsResponse = await response.json();
    console.log("[API Client] Successfully fetched simulation details:", data);
    return data;
  } catch (error) {
    console.error("[API Client] Error in getSimulationDetails:", error);
    if (error instanceof Error) {
      throw error;
    } else {
      throw new Error(
        "An unknown error occurred while fetching simulation details."
      );
    }
  }
};

// You can add other simulation-related API functions here in the future
// export const startPersonaSimulation = async (...) => { ... };

/**
 * Sends a simulated incoming message content to the backend to be enqueued
 * for processing, mimicking a message received from the simulated contact.
 *
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {string} conversationId - The UUID of the target simulation conversation.
 * @param {string} content - The text content of the message to simulate.
 * @returns {Promise<SimulationMessageEnqueueResponse>} A promise resolving to the enqueue confirmation from the API.
 * @throws {Error} If the API call fails (e.g., network error, non-OK status code).
 */
export const sendSimulationMessage = async (
  fetcher: FetchFunction,
  conversationId: string,
  content: string
): Promise<SimulationMessageEnqueueResponse> => {
  // Construct the specific endpoint URL
  const endpoint = `${SIMULATION_API_PREFIX}/conversations/${conversationId}/messages`;
  console.log(`[API Client] Sending simulation message to: ${endpoint}`); // Optional logging

  // Prepare the request body according to the SimulationMessageCreate schema
  const payload: SimulationMessageCreate = { content };

  try {
    // Make the authenticated POST request
    const response = await fetcher(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    // Check if the request was accepted (status code 202) or failed
    if (!response.ok) {
      // Checks for 2xx status codes, including 202
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        console.warn(
          "[API Client] Could not parse error response body as JSON.",
          e
        );
      }
      throw new Error(`Failed to enqueue simulation message: ${errorDetail}`);
    }

    // Parse the successful JSON response (confirmation details)
    const data: SimulationMessageEnqueueResponse = await response.json();
    console.log("[API Client] Successfully enqueued simulation message:", data); // Optional logging
    return data;
  } catch (error) {
    console.error("[API Client] Error in sendSimulationMessage:", error);
    if (error instanceof Error) {
      throw error;
    } else {
      throw new Error(
        "An unknown error occurred while sending the simulation message."
      );
    }
  }
};

export const deleteSimulationCheckpoint = async (
  fetcher: FetchFunction,
  conversationId: string
): Promise<void> => {
  const endpoint = `/api/v1/simulation/conversations/${conversationId}/checkpoint`;
  console.log(`[API Client] Deleting simulation checkpoint: ${endpoint}`);
  try {
    const response = await fetcher(endpoint, { method: "DELETE" });
    if (!response.ok && response.status !== 204) {
      // 204 is success for DELETE
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {}
      throw new Error(`Failed to delete simulation checkpoint: ${errorDetail}`);
    }
    console.log("[API Client] Successfully deleted simulation checkpoint.");
  } catch (error) {
    console.error("[API Client] Error in deleteSimulationCheckpoint:", error);
    if (error instanceof Error) {
      throw error;
    } else {
      throw new Error(
        "An unknown error occurred while deleting the simulation checkpoint."
      );
    }
  }
};
