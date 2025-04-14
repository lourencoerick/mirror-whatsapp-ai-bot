/* eslint-disable @typescript-eslint/no-unused-vars */
import {
  ContactImportJobStatusResponse,
  PaginatedImportJobListResponse,
} from "@/types/contact-import";

import { Contact } from '@/types/contact'; 
import { FetchFunction } from '@/hooks/use-authenticated-fetch'; // Adjust path

/**
 * Fetches the status of a specific contact import job.
 * This function is designed to be used as a fetcher by SWR.
 *
 * @param {string} jobId - The ID of the job to be fetched.
 * @param {Function} fetcher - The authenticated fetch function (e.g., provided by useAuthenticatedFetch).
 *                             It is expected to return a standard Response object.
 * @returns {Promise<ContactImportJobStatusResponse>} A promise that resolves with the job status details.
 * @throws {Error} Throws an error if the request fails or the job is not found.
 */
export const getContactImportJobStatus = async (
  jobId: string,
  fetcher: FetchFunction
): Promise<ContactImportJobStatusResponse> => {
  if (!jobId) {
    throw new Error("Job ID is required to fetch status.");
  }

  const endpointPath = `/api/v1/contacts/batch/import/status/${jobId}`;

  try {
    const response = await fetcher(endpointPath, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });

    if (response.ok) {
      const data: ContactImportJobStatusResponse = await response.json();
      console.log(data);

      if (!data.id || !data.status) {
        throw new Error("Invalid job status response received from API.");
      }
      console.log(data);
      return data;
    } else if (response.status === 404) {
      throw new Error(`Import job with ID '${jobId}' not found.`);
    } else {
      let errorMessage = `Failed to fetch job status (${response.status})`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || JSON.stringify(errorData);
      } catch (e) {
        errorMessage = `${errorMessage} - ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }
  } catch (error) {
    console.error(`Error fetching status for job ${jobId}:`, error);
    if (error instanceof Error) {
      throw error;
    } else {
      throw new Error("An unknown error occurred while fetching job status.");
    }
  }
};

/**
 * Fetches a paginated list of contact import jobs.
 * @param {number} page - The page number to fetch (1-indexed).
 * @param {number} size - The number of items per page.
 * @param {Function} fetcher - The authenticated fetch function instance.
 * @returns {Promise<PaginatedImportJobListResponse>} A promise resolving to the paginated list of jobs.
 * @throws {Error} If the network request fails or the API returns an error status.
 */
export const listContactImportJobs = async (
  page: number,
  size: number,
  fetcher: FetchFunction
): Promise<PaginatedImportJobListResponse> => {
  const endpoint = `/api/v1/contacts/batch/import/jobs?page=${page}&size=${size}`;
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
    } catch (e) {}
    throw new Error(`Failed to fetch import jobs: ${errorDetail}`);
  }

  const data: PaginatedImportJobListResponse = await response.json();
  return data;
};




/**
 * Searches for contacts based on a query string.
 * @param {string} query - The search term.
 * @param {number} limit - Maximum number of results to return.
 * @param {AuthenticatedFetchFunction} fetchFn - The authenticated fetch function instance.
 * @returns {Promise<Contact[]>} A promise resolving to an array of matching contacts.
 * @throws {Error} If the network request fails or the API returns an error status.
 */
export const searchContacts = async (
  query: string,
  limit: number = 10, // Default limit for search results
  fetchFn: FetchFunction
): Promise<Contact[]> => {
  // Only search if query is not empty (optional, API might handle this)
  if (!query.trim()) {
    return [];
  }

  const endpoint = `/api/v1/contacts?search=${encodeURIComponent(query)}&limit=${limit}`;
  const response = await fetchFn(endpoint, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    let errorDetail = `API returned status ${response.status}`;
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch (e) { /* Ignore */ }
    throw new Error(`Failed to search contacts: ${errorDetail}`);
  }

  // Assuming the API returns a PaginatedContact structure even for search
  // If it returns just Contact[], adjust accordingly
  const data: { items: Contact[] } = await response.json(); // Adjust based on actual API response structure
  return data.items || []; // Return the items array
};