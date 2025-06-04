/* eslint-disable @typescript-eslint/no-unused-vars */
// src/lib/api/knowledge.ts

import { FetchFunction } from "@/hooks/use-authenticated-fetch";
import { components } from "@/types/api"; // API type definitions

// --- API Types ---
type IngestResponse = components["schemas"]["IngestResponse"];
type AddUrlRequest = components["schemas"]["AddUrlRequest"];
type AddTextRequest = components["schemas"]["AddTextRequest"];

// type KnowledgeDocumentRead = components["schemas"]["KnowledgeDocumentRead"];
type PaginatedKnowledgeDocumentRead =
  components["schemas"]["PaginatedKnowledgeDocumentRead"];

const KNOWLEDGE_API_PREFIX = "/api/v1/knowledge"; // API Prefix

/**
 * Calls the backend API to add a URL for knowledge ingestion.
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {AddUrlRequest} payload - The URL string to ingest.
 * @returns {Promise<IngestResponse>} A promise resolving to the IngestResponse.
 * @throws {Error} If the API call fails.
 */
export const addKnowledgeUrl = async (
  fetcher: FetchFunction,
  payload: AddUrlRequest 
): Promise<IngestResponse> => {
  const response = await fetcher(`${KNOWLEDGE_API_PREFIX}/add-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
    throw new Error(`Failed to add URL: ${errorDetail}`);
  }
  return response.json();
};

/**
 * Uploads a knowledge file using FormData.
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {File} file - The file to upload.
 * @returns {Promise<IngestResponse>} A promise resolving to the IngestResponse.
 * @throws {Error} If the API call fails.
 */
export const addKnowledgeFile = async (
  fetcher: FetchFunction,
  file: File
): Promise<IngestResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  // Don't set Content-Type header manually for FormData, browser handles it with boundary
  const response = await fetcher(`${KNOWLEDGE_API_PREFIX}/upload-file`, {
    method: "POST",
    body: formData,
    headers: { Accept: "application/json", "Content-Type": "" },
  });

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) {
      /* Ignore parsing error */
    }
    throw new Error(`Failed to upload file: ${errorDetail}`);
  }
  return response.json();
};

/**
 * Adds a new knowledge document from text content.
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {string} title - The title for the text document.
 * @param {string} textContent - The text content.
 * @param {string} [description] - Optional description.
 * @returns {Promise<IngestResponse>} A promise resolving to the IngestResponse.
 * @throws {Error} If the API call fails.
 */
export const addKnowledgeText = async (
  fetcher: FetchFunction,
  title: string,
  textContent: string,
  description?: string
): Promise<IngestResponse> => {
  const payload: AddTextRequest = {
    title,
    content: textContent,
  };
  const response = await fetcher(`${KNOWLEDGE_API_PREFIX}/add-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
    throw new Error(`Failed to add text content: ${errorDetail}`);
  }
  return response.json();
};

/**
 * Fetches a paginated list of knowledge documents for the current account.
 * @param {FetchFunction} fetcher - The authenticated fetch function.
 * @param {number} skip - Number of documents to skip (default: 0).
 * @param {number} limit - Maximum number of documents to return (default: 10).
 * @returns {Promise<PaginatedKnowledgeDocumentRead | null>} A promise resolving to the paginated data or null if fetcher is unavailable.
 * @throws {Error} If the API call fails.
 */
export const getKnowledgeDocuments = async (
  fetcher: FetchFunction,
  skip: number = 0,
  limit: number = 10
): Promise<PaginatedKnowledgeDocumentRead | null> => {
  // NOTE: Your previous code returned null if fetcher wasn't available, keeping that pattern.
  // However, useQuery usually handles the enabled flag better. Consider refactoring later.
  if (!fetcher) return null;

  try {
    const url = new URL(
      `${KNOWLEDGE_API_PREFIX}/documents`,
      window.location.origin
    );
    url.searchParams.append("skip", String(skip));
    url.searchParams.append("limit", String(limit));

    const response = await fetcher(url.pathname + url.search, {
      method: "GET",
    });

    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        /* Ignore parsing error */
      }
      // Match error format of other functions
      throw new Error(`Failed to fetch documents: ${errorDetail}`);
    }

    const data: PaginatedKnowledgeDocumentRead = await response.json();
    return data;
  } catch (error) {
    console.error(
      `API Error fetching documents (skip=${skip}, limit=${limit}):`,
      error
    );
    throw error; // Re-throw for react-query
  }
};

/**
 * Deletes a Knowledge Document by its ID.
 * @param {FetchFunction} fetcher - The authenticated fetch function instance.
 * @param {string} documentId - The ID of the Knowledge Document to delete.
 * @returns {Promise<void>} A promise that resolves when deletion is successful.
 * @throws {Error} If the network request fails, Knowledge Document not found, or API returns an error.
 */
export const deleteKnowledgeDocument = async (
  fetcher: FetchFunction,
  documentId: string
): Promise<void> => {
  if (!documentId) {
    throw new Error("Knowledge Document ID is required for deletion.");
  }
  const endpoint = `${KNOWLEDGE_API_PREFIX}/documents/${documentId}`;
  const response = await fetcher(endpoint, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });

  if (response.status === 204) {
    return; // Success
  }

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    if (response.status === 404) {
      errorDetail = "Knowledge Doc not found";
    } else {
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        /* Ignore parsing error */
      }
    }
    throw new Error(
      `Failed to delete Knowledge Document ${documentId}: ${errorDetail}`
    );
  }

  // Fallback for unexpected OK status other than 204
  console.warn(
    `Delete request for Knowledge Document ${documentId} returned status ${response.status} instead of 204, but was 'ok'.`
  );
};
