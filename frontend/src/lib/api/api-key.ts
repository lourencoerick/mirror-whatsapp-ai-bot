/* eslint-disable @typescript-eslint/no-unused-vars */
/**
 * @file This service handles all API communications related to API Key management.
 */

import { FetchFunction } from "@/hooks/use-authenticated-fetch";
import { components } from "@/types/api";

// Define the types based on our OpenAPI/Pydantic schemas
export type ApiKeyRead = components["schemas"]["ApiKeyRead"];
export type ApiKeyCreatePayload = components["schemas"]["ApiKeyCreate"];
export type ApiKeyReadWithSecret =
  components["schemas"]["ApiKeyReadWithSecret"];

const API_V1_BASE = "/api/v1";

/**
 * Fetches the list of API keys for a specific inbox.
 * @param {string} inboxId - The ID of the inbox.
 * @param {FetchFunction} fetcher - The authenticated fetch function instance.
 * @returns {Promise<ApiKeyRead[]>} A promise that resolves to an array of API keys.
 * @throws {Error} If the network request fails or the API returns an error.
 */
export const listApiKeys = async (
  inboxId: string,
  fetcher: FetchFunction
): Promise<ApiKeyRead[]> => {
  if (!inboxId) {
    throw new Error("Inbox ID is required.");
  }
  const endpoint = `${API_V1_BASE}/inboxes/${inboxId}/api-keys`;
  const response = await fetcher(endpoint, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) {
      /* Ignore parsing error */
    }
    throw new Error(`Failed to fetch API keys: ${errorDetail}`);
  }

  const data: ApiKeyRead[] = await response.json();
  return data;
};

/**
 * Generates a new API key for a specific inbox.
 * This is the only time the full secret key will be returned.
 * @param {string} inboxId - The ID of the inbox.
 * @param {ApiKeyCreatePayload} payload - The data for the new key (name, scopes).
 * @param {FetchFunction} fetcher - The authenticated fetch function instance.
 * @returns {Promise<ApiKeyReadWithSecret>} A promise resolving to the new key, including the secret.
 * @throws {Error} If the network request fails or the API returns an error.
 */
export const generateApiKey = async (
  inboxId: string,
  payload: ApiKeyCreatePayload,
  fetcher: FetchFunction
): Promise<ApiKeyReadWithSecret> => {
  if (!inboxId) {
    throw new Error("Inbox ID is required.");
  }
  const endpoint = `${API_V1_BASE}/inboxes/${inboxId}/api-keys`;
  const response = await fetcher(endpoint, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) {
      /* Ignore parsing error */
    }
    throw new Error(`Failed to generate API key: ${errorDetail}`);
  }

  const data: ApiKeyReadWithSecret = await response.json();
  return data;
};

/**
 * Revokes (deletes) an API key by its ID.
 * @param {string} inboxId - The ID of the inbox the key belongs to.
 * @param {string} apiKeyId - The ID of the API key to delete.
 * @param {FetchFunction} fetcher - The authenticated fetch function instance.
 * @returns {Promise<void>} A promise that resolves when deletion is successful.
 * @throws {Error} If the network request fails or the API returns an error.
 */
export const revokeApiKey = async (
  inboxId: string,
  apiKeyId: string,
  fetcher: FetchFunction
): Promise<void> => {
  if (!inboxId || !apiKeyId) {
    throw new Error("Inbox ID and API Key ID are required for deletion.");
  }
  const endpoint = `${API_V1_BASE}/inboxes/${inboxId}/api-keys/${apiKeyId}`;
  const response = await fetcher(endpoint, {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  // Expecting 204 No Content for successful deletion
  if (response.status === 204) {
    return; // Success
  }

  // Handle other statuses as errors
  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    if (response.status === 404) {
      errorDetail = "API Key or Inbox not found";
    } else {
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        /* Ignore parsing error */
      }
    }
    throw new Error(`Failed to revoke API key ${apiKeyId}: ${errorDetail}`);
  }
};
