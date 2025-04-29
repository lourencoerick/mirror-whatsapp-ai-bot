// services/api/knowledge.ts

import { FetchFunction } from "@/hooks/use-authenticated-fetch";

import { components } from "@/types/api"; // API type definitions
type IngestResponse = components["schemas"]["IngestResponse"];
type AddUrlRequest = components["schemas"]["AddUrlRequest"];
type KnowledgeDocumentRead = components["schemas"]["KnowledgeDocumentRead"];
type PaginatedKnowledgeDocumentRead =
  components["schemas"]["PaginatedKnowledgeDocumentRead"];

const KNOWLEDGE_API_PREFIX = "/api/v1/knowledge"; // Prefixo da API

/**
 * Calls the backend API to add a URL for knowledge ingestion.
 * @param url - The URL string to ingest.
 * @returns A promise resolving to the IngestResponse or null on error.
 */
export const addKnowledgeUrl = async (
  fetcher: FetchFunction,
  url: string
): Promise<IngestResponse | null> => {
  try {
    // O schema AddUrlRequest espera um objeto { url: "..." }
    const payload: AddUrlRequest = { url };

    const response = await fetcher(`${KNOWLEDGE_API_PREFIX}/add-url`, {
      method: "POST",
      headers: {
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
      throw new Error(`Failed to fetch inboxes: ${errorDetail}`);
    }

    const data: IngestResponse = await response.json();
    return data;
  } catch (error) {
    console.error("API Error adding knowledge URL:", error);
    // Re-throw or handle error appropriately for UI
    throw error; // Lançar para que o form possa pegar
  }
};

/**
 * Fetches a paginated list of knowledge documents for the current account.
 * @param fetcher - The authenticated fetch function.
 * @param skip - Number of documents to skip.
 * @param limit - Maximum number of documents to return.
 * @returns A promise resolving to an object containing the items and total count, or null on error.
 */
export const getKnowledgeDocuments = async (
  fetcher: FetchFunction,
  skip: number = 0, // Adicionar parâmetro skip com default 0
  limit: number = 10 // Adicionar parâmetro limit com default
): Promise<PaginatedKnowledgeDocumentRead[] | null> => {
  // Modificar tipo de retorno
  try {
    // Construir a URL com query parameters para skip e limit
    const url = new URL(
      `${KNOWLEDGE_API_PREFIX}/documents`,
      window.location.origin
    ); // Usar URL para facilitar adição de params
    url.searchParams.append("skip", String(skip));
    url.searchParams.append("limit", String(limit));

    // Chamar a API com a URL construída
    const response = await fetcher(
      // Esperar o tipo KnowledgeDocumentList
      url.pathname + url.search, // Passar path + query string para o fetcher
      { method: "GET" }
    );

    if (!response.ok) {
      let errorDetail = `API returned status ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        /* Ignore parsing error */
      }
      throw new Error(`Failed to fetch inboxes: ${errorDetail}`);
    }

    const data: PaginatedKnowledgeDocumentRead[] = await response.json();
    return data;
  } catch (error) {
    console.error(
      `API Error fetching documents (skip=${skip}, limit=${limit}):`,
      error
    );
    throw error; // Lançar para react-query tratar
  }
};

/**
 * Deletes an Knowledge Document by its ID.
 * @param {string} documentId - The ID of the Knowledge Document to delete.
 * @param {FetchFunction} fetcher - The authenticated fetch function instance.
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
    headers: {
      Accept: "application/json", // Even if no content, good practice
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
      errorDetail = "Knowledge Doc not found";
    } else {
      try {
        // Attempt to parse error detail, but DELETE might not have a body
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

  // Should not happen if status is 204, but as a fallback
  if (response.ok && response.status !== 204) {
    console.warn(
      `Delete request for Knowledge Document ${documentId} returned status ${response.status} instead of 204, but was 'ok'.`
    );
    return;
  }
};
