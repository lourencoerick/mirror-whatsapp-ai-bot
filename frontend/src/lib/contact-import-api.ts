import {
  ContactImportJobStatusResponse,
  PaginatedImportJobListResponse,
} from "@/types/contact-import";

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
  fetcher: (url: string, options?: RequestInit) => Promise<Response>
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
  fetcher: (url: string, options?: RequestInit) => Promise<Response>
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
